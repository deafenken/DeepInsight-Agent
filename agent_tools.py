import json
import sqlite3
from pathlib import Path

from retriever import DEEPSEEK_CHAT_MODEL, DeepSeekClient, SYSTEM_PROMPT, call_llm_serial, get_connection

DEFAULT_DB_PATH = Path("/Volumes/ORICO/code1/data/enterprise_analysis.db")


def fetch_company_row(conn, company_name):
    row = conn.execute("SELECT company_id, company_name FROM dim_company WHERE company_name = ?", (company_name,)).fetchone()
    if not row:
        raise ValueError(f"未找到公司: {company_name}")
    return dict(row)


def tool_get_equity_penetration(company_name, max_depth=2, db_path=DEFAULT_DB_PATH):
    """查询指定公司的股权穿透结果，返回图谱节点与边关系 JSON。"""
    conn = get_connection(db_path)
    try:
        company = fetch_company_row(conn, company_name)
        sql = """
        WITH RECURSIVE equity_tree AS (
            SELECT
                fir.relation_id,
                fir.investor_party_id,
                fir.investee_company_id,
                fir.equity_ratio,
                1 AS depth,
                dc.company_name AS investee_name,
                COALESCE(dc2.company_name, dpn.person_name, '未知投资方') AS investor_name,
                CASE WHEN dp.company_id IS NOT NULL THEN 'company' ELSE 'person' END AS investor_type,
                fir.equity_ratio AS cumulative_ratio
            FROM fact_investment_relation fir
            JOIN dim_party dp ON fir.investor_party_id = dp.party_id
            LEFT JOIN dim_company dc2 ON dp.company_id = dc2.company_id
            LEFT JOIN dim_person dpn ON dp.person_id = dpn.person_id
            JOIN dim_company dc ON fir.investee_company_id = dc.company_id
            WHERE dp.company_id = ?

            UNION ALL

            SELECT
                fir.relation_id,
                fir.investor_party_id,
                fir.investee_company_id,
                fir.equity_ratio,
                et.depth + 1 AS depth,
                dc.company_name AS investee_name,
                COALESCE(dc2.company_name, dpn.person_name, '未知投资方') AS investor_name,
                CASE WHEN dp.company_id IS NOT NULL THEN 'company' ELSE 'person' END AS investor_type,
                ROUND(et.cumulative_ratio * fir.equity_ratio / 100.0, 4) AS cumulative_ratio
            FROM equity_tree et
            JOIN dim_party dp_parent ON dp_parent.company_id = et.investee_company_id
            JOIN fact_investment_relation fir ON fir.investor_party_id = dp_parent.party_id
            JOIN dim_party dp ON fir.investor_party_id = dp.party_id
            LEFT JOIN dim_company dc2 ON dp.company_id = dc2.company_id
            LEFT JOIN dim_person dpn ON dp.person_id = dpn.person_id
            JOIN dim_company dc ON fir.investee_company_id = dc.company_id
            WHERE et.depth < ?
        )
        SELECT * FROM equity_tree
        ORDER BY depth, cumulative_ratio DESC, investee_name
        """
        rows = [dict(row) for row in conn.execute(sql, (company["company_id"], max_depth)).fetchall()]
        nodes = [{"id": f"company-{company['company_id']}", "company_id": company["company_id"], "name": company["company_name"], "type": "root", "level": 0}]
        seen_nodes = {nodes[0]["id"]}
        edges = []
        for row in rows:
            source_id = f"party-{row['investor_party_id']}"
            target_id = f"company-{row['investee_company_id']}"
            if source_id not in seen_nodes:
                nodes.append({
                    "id": source_id,
                    "company_id": None,
                    "name": row["investor_name"],
                    "type": row["investor_type"],
                    "level": max(0, row["depth"] - 1),
                })
                seen_nodes.add(source_id)
            if target_id not in seen_nodes:
                nodes.append({
                    "id": target_id,
                    "company_id": row["investee_company_id"],
                    "name": row["investee_name"],
                    "type": "company",
                    "level": row["depth"],
                })
                seen_nodes.add(target_id)
            edges.append(
                {
                    "source": source_id,
                    "target": target_id,
                    "ratio": row["equity_ratio"],
                    "cumulative_ratio": row["cumulative_ratio"],
                    "depth": row["depth"],
                }
            )
        return {
            "root_company": company["company_name"],
            "nodes": nodes,
            "edges": edges,
            "summary": {"node_count": len(nodes), "edge_count": len(edges)},
        }
    finally:
        conn.close()


def tool_get_risk_radar(company_name, include_subsidiaries=False, db_path=DEFAULT_DB_PATH):
    """查询指定公司近三年的司法风险与行政处罚，并按严重程度汇总。"""
    conn = get_connection(db_path)
    try:
        company = fetch_company_row(conn, company_name)
        company_ids = [company["company_id"]]
        if include_subsidiaries:
            company_ids.extend(
                item["company_id"]
                for item in tool_get_equity_penetration(company_name, db_path=db_path)["nodes"]
                if item["id"].startswith("company-") and item["company_id"] and item["name"] != company_name
            )
        placeholders = ",".join("?" for _ in company_ids)
        sql = f"""
        SELECT c.company_name, flr.risk_type, flr.filing_date, flr.amount_involved, flr.severity_score, flr.detail_text
        FROM fact_legal_risk flr
        JOIN dim_company c ON flr.company_id = c.company_id
        WHERE flr.company_id IN ({placeholders})
          AND flr.filing_date >= date('now', '-3 years')
        ORDER BY flr.severity_score DESC, flr.filing_date DESC
        """
        rows = [dict(row) for row in conn.execute(sql, company_ids).fetchall()]
        severity_buckets = {"高": 0, "中": 0, "低": 0}
        total_amount = 0.0
        for row in rows:
            score = row["severity_score"]
            if score >= 80:
                severity_buckets["高"] += 1
            elif score >= 50:
                severity_buckets["中"] += 1
            else:
                severity_buckets["低"] += 1
            total_amount += row.get("amount_involved") or 0.0
        return {
            "company_name": company_name,
            "dimensions": {
                "高风险事件数": severity_buckets["高"],
                "中风险事件数": severity_buckets["中"],
                "低风险事件数": severity_buckets["低"],
                "风险事件总数": len(rows),
                "涉案金额合计": round(total_amount, 2),
            },
            "details": rows,
        }
    finally:
        conn.close()


def tool_get_innovation_index(company_name, db_path=DEFAULT_DB_PATH):
    """聚合查询指定公司的专利数量与趋势，评估其创新能力。"""
    conn = get_connection(db_path)
    try:
        company = fetch_company_row(conn, company_name)
        sql = """
        SELECT application_year, patent_type, COUNT(*) AS patent_count, AVG(COALESCE(patent_score, 0)) AS avg_score
        FROM fact_ip_patent
        WHERE company_id = ?
        GROUP BY application_year, patent_type
        ORDER BY application_year, patent_type
        """
        rows = [dict(row) for row in conn.execute(sql, (company["company_id"],)).fetchall()]
        total_patents = sum(row["patent_count"] for row in rows)
        invention_count = sum(row["patent_count"] for row in rows if row["patent_type"] == "发明")
        recent_rows = [row for row in rows if row["application_year"] >= max((item["application_year"] for item in rows), default=0) - 2]
        avg_score = round(sum((row["avg_score"] or 0) * row["patent_count"] for row in rows) / total_patents, 2) if total_patents else 0
        return {
            "company_name": company_name,
            "dimensions": {
                "专利总量": total_patents,
                "发明占比": round((invention_count / total_patents * 100), 2) if total_patents else 0,
                "近三年活跃度": sum(row["patent_count"] for row in recent_rows),
                "平均专利评分": avg_score,
                "专利类型覆盖数": len({row["patent_type"] for row in rows}),
            },
            "details": rows,
        }
    finally:
        conn.close()


def build_radar_scores(risk_data, innovation_data):
    risk_dimensions = risk_data.get("dimensions") or {}
    innovation_dimensions = innovation_data.get("dimensions") or {}
    risk_count = risk_dimensions.get("风险事件总数", 0)
    high_risk = risk_dimensions.get("高风险事件数", 0)
    innovation_score = innovation_dimensions.get("平均专利评分", 0)
    return {
        "财务健康度": 70,
        "创新能力": min(100, int(innovation_score or 0)),
        "市场占有率": 60,
        "合规风险": max(10, 100 - high_risk * 15 - risk_count * 3),
        "供应链稳定性": 65,
    }


def build_sources_from_tools(equity_data, risk_data, innovation_data):
    sources = []
    sources.append({"type": "tool", "label": f"股权穿透：{equity_data['root_company']}", "snippet": json.dumps(equity_data['summary'], ensure_ascii=False)})
    sources.append({"type": "tool", "label": f"风险雷达：{risk_data['company_name']}", "snippet": json.dumps(risk_data['dimensions'], ensure_ascii=False)})
    sources.append({"type": "tool", "label": f"创新指数：{innovation_data['company_name']}", "snippet": json.dumps(innovation_data['dimensions'], ensure_ascii=False)})
    return sources


def build_viz_blocks(equity_data, risk_data, innovation_data):
    graph_nodes = []
    categories = {"root": 0, "company": 1, "person": 2}
    for node in equity_data["nodes"]:
        graph_nodes.append(
            {
                "name": node["name"],
                "value": node["level"],
                "category": categories.get(node["type"], 1),
                "symbolSize": 38 if node["type"] == "root" else 26,
            }
        )
    graph_links = [
        {
            "source": next(item["name"] for item in equity_data["nodes"] if item["id"] == edge["source"]),
            "target": next(item["name"] for item in equity_data["nodes"] if item["id"] == edge["target"]),
            "value": edge["ratio"],
        }
        for edge in equity_data["edges"]
    ]
    radar_scores = build_radar_scores(risk_data, innovation_data)
    return [
        {
            "type": "graph",
            "title": f"{equity_data['root_company']} 股权关系图谱",
            "option": {
                "tooltip": {"formatter": "{b}"},
                "legend": [{"data": ["核心公司", "公司", "个人"]}],
                "series": [
                    {
                        "type": "graph",
                        "layout": "force",
                        "roam": True,
                        "label": {"show": True},
                        "categories": [{"name": "核心公司"}, {"name": "公司"}, {"name": "个人"}],
                        "data": graph_nodes,
                        "links": graph_links,
                        "force": {"repulsion": 260, "edgeLength": [90, 180]},
                        "lineStyle": {"curveness": 0.1},
                    }
                ],
            },
        },
        {
            "type": "radar",
            "title": f"{risk_data['company_name']} 风险与创新雷达图",
            "option": {
                "tooltip": {},
                "radar": {
                    "indicator": [
                        {"name": key, "max": 100} for key in radar_scores.keys()
                    ]
                },
                "series": [
                    {
                        "type": "radar",
                        "data": [
                            {
                                "value": list(radar_scores.values()),
                                "name": risk_data['company_name'],
                            }
                        ],
                    }
                ],
            },
        },
    ]


def build_context_for_llm(question, equity_data, risk_data, innovation_data):
    return "\n\n".join(
        [
            f"问题：{question}",
            f"股权穿透：{json.dumps(equity_data, ensure_ascii=False)}",
            f"风险雷达：{json.dumps(risk_data, ensure_ascii=False)}",
            f"创新指数：{json.dumps(innovation_data, ensure_ascii=False)}",
        ]
    )


def route_advanced_question(question, company_name, client=None):
    if client:
        prompt = [
            {"role": "system", "content": "你是高级工具路由器，只输出 JSON。需要字段：needs_equity, needs_risk, needs_innovation。值只能是 true 或 false。"},
            {"role": "user", "content": json.dumps({"question": question, "company_name": company_name}, ensure_ascii=False)},
        ]
        raw = call_llm_serial(client, "advanced_router", prompt)
        try:
            data = json.loads(raw.strip().strip("`").replace("json", "", 1))
            return {
                "needs_equity": bool(data.get("needs_equity", True)),
                "needs_risk": bool(data.get("needs_risk", True)),
                "needs_innovation": bool(data.get("needs_innovation", False)),
            }
        except Exception:
            pass
    return {
        "needs_equity": any(keyword in question for keyword in ["股权", "控股", "子公司", "穿透"]),
        "needs_risk": any(keyword in question for keyword in ["风险", "处罚", "司法", "合规"]),
        "needs_innovation": any(keyword in question for keyword in ["专利", "创新", "研发"]),
    }


def run_advanced_analysis(question, company_name, db_path=DEFAULT_DB_PATH, client=None):
    company_name = company_name.strip()
    route = route_advanced_question(question, company_name, client)
    equity_data = tool_get_equity_penetration(company_name, db_path=db_path) if route["needs_equity"] or route["needs_risk"] else {"root_company": company_name, "nodes": [], "edges": [], "summary": {"node_count": 0, "edge_count": 0}}
    risk_data = tool_get_risk_radar(company_name, include_subsidiaries=route["needs_equity"] and route["needs_risk"], db_path=db_path) if route["needs_risk"] else {"company_name": company_name, "dimensions": {}, "details": []}
    innovation_data = tool_get_innovation_index(company_name, db_path=db_path) if route["needs_innovation"] else {"company_name": company_name, "dimensions": {}, "details": []}
    context = build_context_for_llm(question, equity_data, risk_data, innovation_data)
    if client is None:
        client = DeepSeekClient(chat_model=DEEPSEEK_CHAT_MODEL)
    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT.format(retrieved_context=context),
        },
        {"role": "user", "content": question},
    ]
    answer = call_llm_serial(client, "advanced_answer", messages, temperature=0.2)
    return {
        "answer_markdown": answer,
        "sources": build_sources_from_tools(equity_data, risk_data, innovation_data),
        "viz_blocks": build_viz_blocks(equity_data, risk_data, innovation_data),
        "tool_results": {
            "equity": equity_data,
            "risk": risk_data,
            "innovation": innovation_data,
        },
    }

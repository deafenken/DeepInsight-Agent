# Streamlit 页面初始化问题

严重级别：高

## 问题

`app_advanced.py` 导入了 `app.py` 中的多个函数；而 `app.py` 在模块顶层就调用了 `st.set_page_config(...)`。这意味着当 `app_advanced.py` 运行时，`app.py` 的顶层代码会先执行一次 `set_page_config`，随后 `app_advanced.py` 自己又执行一次。

Streamlit 对 `set_page_config` 的调用顺序比较敏感，通常要求它是页面中的首次且单次配置。这个结构非常容易触发页面初始化异常。

## 代码位置

- [app.py](/Volumes/ORICO/code1/app.py#L8)
- [app_advanced.py](/Volumes/ORICO/code1/app_advanced.py#L8)
- [app_advanced.py](/Volumes/ORICO/code1/app_advanced.py#L11)

## 影响

- 高级分析页可能在启动时直接报错
- 即使不报错，也让页面配置耦合在一起，不利于后续拆分多页面应用

## 建议

- 把 `build_sidebar`、`load_filters`、`render_sources` 等公共函数拆到独立的工具模块
- 保证每个 Streamlit 页面只在自己的入口文件里调用一次 `st.set_page_config(...)`

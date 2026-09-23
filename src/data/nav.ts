// 导航配置：10 项 = 9 主项（上）+ 帮助（置底）

export type NavPosition = "top" | "bottom";

export interface NavItem {
  /** 路由 key */
  key: string;
  /** 中文标签 */
  label: string;
  /** 图标：内置 SVG 标识（home/tools/settings 与 tab_* 系列） */
  icon: string;
  position: NavPosition;
  /** 该页对应的功能要点摘要 */
  summary: string;
}

export const NAV_ITEMS: NavItem[] = [
  {
    key: "home",
    label: "主页",
    icon: "home",
    position: "top",
    summary: "左栏项目经费概览卡片 + 右栏任务进度卡片；点击卡片跳转；项目/预算/支出/进度变更后刷新",
  },
  {
    key: "project-list",
    label: "项目清单",
    icon: "tab_project",
    position: "top",
    summary: "8 列表格 CRUD、右键复制行、JSON 导入导出、级联删除（预算/支出/甘特/文档/成果）+ 清理附件目录",
  },
  {
    key: "project-fund",
    label: "项目经费",
    icon: "tab_fund",
    position: "top",
    summary: "三级预算树 + 执行率进度条列 + ECharts 饼图（类别/时间分布两种视图）+ 从预算编制导入",
  },
  {
    key: "project-progress",
    label: "项目进度",
    icon: "tab_progress",
    position: "top",
    summary: "jQueryGantt 复用，Tauri IPC 桥；任务增删改/拖拽/里程碑/依赖/导出 XLSX/JSON/CSV",
  },
  {
    key: "project-document",
    label: "项目文档",
    icon: "tab_document",
    position: "top",
    summary: "7 列表格 + 关键词/类型筛选 + 附件管理（上传/查看/下载/删除）+ Excel 导出 + CRUD 对话框",
  },
  {
    key: "project-outcome",
    label: "项目成果",
    icon: "tab_outcome",
    position: "top",
    summary: "9 列表格（名称/类型/状态/作者/提交/发表/期刊/备注/附件）+ 筛选 + 附件 + Excel 导出",
  },
  {
    key: "activity",
    label: "学术活动",
    icon: "tab_activity",
    position: "top",
    summary: "9 列表格 + 关键词/类型/状态/日期筛选 + 附件 + Excel 导出 + ActivityDialog",
  },
  {
    key: "budgeting",
    label: "预算编制",
    icon: "tab_budget",
    position: "top",
    summary: "三级可编辑树、单价×数量联动、父项递归汇总、明细/汇总/分年度比例导出",
  },
  {
    key: "tools",
    label: "小工具",
    icon: "tools",
    position: "top",
    summary: "间接经费二分法计算器（费率阶梯 20%/15%/13%）+ 树形列表工具（增删/批量/导入导出）",
  },
  {
    key: "settings",
    label: "设置",
    icon: "settings",
    position: "bottom",
    summary:
      "外观主题（浅色/深色/跟随系统）、数据库管理（查看/切换/恢复默认）、系统维护（重建支出统计）、软件简介、使用帮助、操作日志（100 条上限，JSON 字段级 diff）",
  },
];

export const DEFAULT_PAGE = "home";

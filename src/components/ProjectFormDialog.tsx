import { useState, useEffect } from "react";

// 表单数据接口，对应后端 ProjectNew
export interface ProjectFormData {
  name: string;
  financial_code: string;
  project_code: string;
  project_type: string;
  start_date: string;
  end_date: string;
  total_budget: string;
  director: string;
}

// 项目数据接口，对应后端 Project
interface Project {
  id: number;
  name: string;
  financial_code: string | null;
  project_code: string | null;
  project_type: string | null;
  leader: string | null;
  start_date: string | null;
  end_date: string | null;
  total_budget: number | null;
  director: string | null;
}

interface Props {
  title: string;
  initialProject?: Project | null;
  onSubmit: (data: ProjectFormData) => Promise<void>;
  onClose: () => void;
}

// 将 Project 接口数据转换为表单数据（处理 null 值）
const projectToFormData = (project?: Project | null): ProjectFormData => ({
  name: project?.name ?? "",
  financial_code: project?.financial_code ?? "",
  project_code: project?.project_code ?? "",
  project_type: project?.project_type ?? "",
  start_date: project?.start_date ?? "",
  end_date: project?.end_date ?? "",
  total_budget: project?.total_budget?.toString() ?? "",
  director: project?.director ?? "",
});

export default function ProjectFormDialog({
  title,
  initialProject,
  onSubmit,
  onClose,
}: Props) {
  const [formData, setFormData] = useState<ProjectFormData>(() =>
    projectToFormData(initialProject)
  );
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 当 initialProject 变化时（例如打开另一个项目进行编辑），重置表单
  useEffect(() => {
    setFormData(projectToFormData(initialProject));
    setError(null);
  }, [initialProject]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    // 简单验证：项目名称必填
    if (!formData.name.trim()) {
      setError("项目名称不能为空");
      return;
    }

    // 验证总经费是否为有效数字
    if (formData.total_budget && isNaN(parseFloat(formData.total_budget))) {
      setError("总经费必须是数字");
      return;
    }

    setIsSubmitting(true);
    try {
      // 传递数据给父组件处理（父组件负责调用 Tauri 命令）
      await onSubmit(formData);
      onClose(); // 成功后关闭对话框
    } catch (err) {
      setError(String(err));
      setIsSubmitting(false);
    }
  };

  return (
    <div className="dialog-overlay">
      <div className="dialog-container">
        <div className="dialog-header">
          <h2>{title}</h2>
          <button className="close-btn" onClick={onClose} disabled={isSubmitting}>
            &times;
          </button>
        </div>
        <form onSubmit={handleSubmit} className="dialog-body">
          {error && <div className="form-error">{error}</div>}
          <div className="form-grid">
            <div className="form-group">
              <label htmlFor="name">项目名称 *</label>
              <input
                type="text"
                id="name"
                name="name"
                value={formData.name}
                onChange={handleChange}
                required
              />
            </div>
            <div className="form-group">
              <label htmlFor="financial_code">财务编号</label>
              <input
                type="text"
                id="financial_code"
                name="financial_code"
                value={formData.financial_code}
                onChange={handleChange}
              />
            </div>
            <div className="form-group">
              <label htmlFor="project_code">项目编号</label>
              <input
                type="text"
                id="project_code"
                name="project_code"
                value={formData.project_code}
                onChange={handleChange}
              />
            </div>
            <div className="form-group">
              <label htmlFor="project_type">项目类别</label>
              <input
                type="text"
                id="project_type"
                name="project_type"
                value={formData.project_type}
                onChange={handleChange}
              />
            </div>
            <div className="form-group">
              <label htmlFor="start_date">开始日期</label>
              <input
                type="date"
                id="start_date"
                name="start_date"
                value={formData.start_date}
                onChange={handleChange}
              />
            </div>
            <div className="form-group">
              <label htmlFor="end_date">结束日期</label>
              <input
                type="date"
                id="end_date"
                name="end_date"
                value={formData.end_date}
                onChange={handleChange}
              />
            </div>
            <div className="form-group">
              <label htmlFor="total_budget">总经费 (万元)</label>
              <input
                type="number"
                step="0.01"
                id="total_budget"
                name="total_budget"
                value={formData.total_budget}
                onChange={handleChange}
              />
            </div>
            <div className="form-group">
              <label htmlFor="director">负责人</label>
              <input
                type="text"
                id="director"
                name="director"
                value={formData.director}
                onChange={handleChange}
              />
            </div>
          </div>
          <div className="dialog-footer">
            <button type="button" onClick={onClose} disabled={isSubmitting}>
              取消
            </button>
            <button type="submit" disabled={isSubmitting} className="primary-btn">
              {isSubmitting ? "保存中..." : "保存"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

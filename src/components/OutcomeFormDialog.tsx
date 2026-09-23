// 成果对话框：新增 / 编辑共用
// 校验规则：仅成果名称必填。
// 注意：本对话框不含附件字段（附件通过列表行内按钮创建后单独管理），
// 因此无文件选择器，attachment_path 由页面层以 null 提交。

import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";

// 全部成果类型/状态中文 label（与后端 core::services::outcome 常量一致）
export const OUTCOME_TYPES = ["论文", "专利", "软著", "标准", "获奖", "其他"];
export const OUTCOME_STATUSES = ["草稿", "已提交", "已接收", "已发表/授权", "已拒绝"];

// 页面层提交用的表单数据（attachment_path 由页面层决定：新增一律 null）
export interface OutcomeFormData {
  name: string;
  type: string;
  status: string | null;
  authors: string | null;
  submit_date: string | null;
  publish_date: string | null;
  journal: string | null;
  description: string | null;
}

// 与后端 core::models::ProjectOutcome 对齐（get_outcome 返回结构，编辑回填用）
interface ProjectOutcome {
  id: number;
  project_id: number;
  name: string;
  type: string;
  status: string | null;
  authors: string | null;
  submit_date: string | null;
  publish_date: string | null;
  journal: string | null;
  description: string | null;
  remarks: string | null;
  attachment_path: string | null;
}

// 本地时区今天的 YYYY-MM-DD（日期字段默认今天）
const todayLocal = () => {
  const now = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
};

interface Props {
  editingId?: number;
  onSubmit: (data: OutcomeFormData, id?: number) => Promise<void>;
  onClose: () => void;
}

export default function OutcomeFormDialog({
  editingId,
  onSubmit,
  onClose,
}: Props) {
  const isEdit = editingId !== undefined;
  const [isLoadingDetail, setIsLoadingDetail] = useState(isEdit);
  const [name, setName] = useState("");
  const [type, setType] = useState<string>(OUTCOME_TYPES[0]);
  const [status, setStatus] = useState<string>(OUTCOME_STATUSES[0]);
  const [authors, setAuthors] = useState("");
  const [submitDate, setSubmitDate] = useState(todayLocal());
  const [publishDate, setPublishDate] = useState(todayLocal());
  const [journal, setJournal] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // 编辑模式：调后端 get_outcome 回填
  useEffect(() => {
    if (!isEdit || editingId === undefined) return;
    (async () => {
      try {
        const detail = await invoke<ProjectOutcome | null>("get_outcome", {
          id: editingId,
        });
        if (!detail) {
          setError("未找到该成果记录，可能已被删除。");
          return;
        }
        setName(detail.name);
        setType(detail.type);
        setStatus(detail.status ?? OUTCOME_STATUSES[0]);
        setAuthors(detail.authors ?? "");
        setSubmitDate(detail.submit_date ?? todayLocal());
        setPublishDate(detail.publish_date ?? todayLocal());
        setJournal(detail.journal ?? "");
        setDescription(detail.description ?? "");
      } catch (err) {
        setError(String(err));
      } finally {
        setIsLoadingDetail(false);
      }
    })();
  }, [isEdit, editingId]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    // 校验：仅名称必填
    if (!name.trim()) {
      setError("成果名称不能为空");
      return;
    }

    const data: OutcomeFormData = {
      name: name.trim(),
      type,
      status: status.trim() || null,
      authors: authors.trim() || null,
      submit_date: submitDate || null,
      publish_date: publishDate || null,
      journal: journal.trim() || null,
      description: description.trim() || null,
    };

    setIsSubmitting(true);
    try {
      await onSubmit(data, editingId);
      onClose();
    } catch (err) {
      setError(String(err));
      setIsSubmitting(false);
    }
  };

  const anyLoading = isSubmitting || isLoadingDetail;
  const title = isEdit ? "编辑成果信息" : "新增成果信息";

  return (
    <div className="dialog-overlay">
      <div className="dialog-container" style={{ width: 560 }}>
        <div className="dialog-header">
          <h2>{title}</h2>
          <button className="close-btn" onClick={() => !anyLoading && onClose()}>
            &times;
          </button>
        </div>
        <form onSubmit={handleSubmit} className="dialog-body">
          {error && <div className="form-error">{error}</div>}
          {isLoadingDetail && <div className="form-info">正在加载成果数据…</div>}

          <div className="form-group">
            <label htmlFor="outcome-name">成果名称 *</label>
            <input
              id="outcome-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="请输入成果名称，必填"
              disabled={isLoadingDetail}
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="outcome-type">成果类型</label>
            <select
              id="outcome-type"
              value={type}
              onChange={(e) => setType(e.target.value)}
              disabled={isLoadingDetail}
            >
              {OUTCOME_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="outcome-status">成果状态</label>
            <select
              id="outcome-status"
              value={status}
              onChange={(e) => setStatus(e.target.value)}
              disabled={isLoadingDetail}
            >
              {OUTCOME_STATUSES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="outcome-authors">作者/完成人</label>
            <textarea
              id="outcome-authors"
              value={authors}
              onChange={(e) => setAuthors(e.target.value)}
              placeholder="请输入作者或完成人"
              rows={3}
              disabled={isLoadingDetail}
            />
          </div>

          <div className="form-group">
            <label htmlFor="outcome-submit-date">投稿/申请日期</label>
            <input
              id="outcome-submit-date"
              type="date"
              value={submitDate}
              onChange={(e) => setSubmitDate(e.target.value)}
              disabled={isLoadingDetail}
            />
          </div>

          <div className="form-group">
            <label htmlFor="outcome-publish-date">发表/授权日期</label>
            <input
              id="outcome-publish-date"
              type="date"
              value={publishDate}
              onChange={(e) => setPublishDate(e.target.value)}
              disabled={isLoadingDetail}
            />
          </div>

          <div className="form-group">
            <label htmlFor="outcome-journal">期刊/授权单位</label>
            <input
              id="outcome-journal"
              type="text"
              value={journal}
              onChange={(e) => setJournal(e.target.value)}
              placeholder="请输入期刊或授权单位"
              disabled={isLoadingDetail}
            />
          </div>

          <div className="form-group">
            <label htmlFor="outcome-description">成果描述</label>
            <textarea
              id="outcome-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="请输入成果描述"
              rows={4}
              disabled={isLoadingDetail}
            />
          </div>

          <div className="dialog-footer">
            <button type="button" onClick={onClose} disabled={anyLoading}>
              取消
            </button>
            <button type="submit" disabled={anyLoading} className="primary-btn">
              {isSubmitting ? "保存中..." : "保存"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
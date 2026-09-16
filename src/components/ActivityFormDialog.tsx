// 活动对话框：新增 / 编辑共用
// 对应 Python app/views/activity_interface.py::ActivityDialog
// 校验与 Python accept 一致：仅活动名称必填。
// 与文档/成果对话框不同：活动对话框自带附件字段
// （Python ActivityDialog 含「选择文件」/「移除附件」按钮，编辑时也可改附件），
// 附件状态由 attachment 字段返回 to 页面层处理（add/replace/delete/none）。

import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { open } from "@tauri-apps/plugin-dialog";

// 全部活动类型/状态中文 label（与后端 core::services::activity 常量一致）
export const ACTIVITY_TYPES = [
  "学术会议",
  "学术讲座",
  "培训活动",
  "研讨会",
  "工作坊",
  "学术交流",
  "其他",
];
export const ACTIVITY_STATUSES = ["未开始", "进行中", "已结束", "已取消"];

// 附件处理状态（对齐 Python ActivityDialog.get_attachment_state）：
// - add     新增附件（old 无）
// - replace 替换附件（拷新 + 删旧）
// - delete  移除已有附件（删文件 + 置空）
// - none    未改动（old 为当前附件路径，供编辑时原样回写）
export interface ActivityAttachmentState {
  action: "add" | "replace" | "delete" | "none";
  oldPath: string | null;
  newFile: string | null;
}

// 页面层提交用的表单数据
export interface ActivityFormData {
  name: string;
  type: string;
  status: string | null;
  organizer: string | null;
  start_date: string | null;
  end_date: string | null;
  location: string | null;
  participants: string | null;
  description: string | null;
  attachment: ActivityAttachmentState;
}

// 与后端 core::models::AcademicActivity 对齐（get_activity 返回结构，编辑回填用）
interface AcademicActivity {
  id: number;
  name: string;
  type: string;
  status: string | null;
  organizer: string | null;
  start_date: string | null;
  end_date: string | null;
  location: string | null;
  participants: string | null;
  description: string | null;
  attachment_path: string | null;
}

// 本地时区今天的 YYYY-MM-DD（对齐 Python DateEdit 默认今天）
const todayLocal = () => {
  const now = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
};

interface Props {
  editingId?: number;
  onSubmit: (data: ActivityFormData, id?: number) => Promise<void>;
  onClose: () => void;
}

export default function ActivityFormDialog({ editingId, onSubmit, onClose }: Props) {
  const isEdit = editingId !== undefined;
  const [isLoadingDetail, setIsLoadingDetail] = useState(isEdit);
  const [name, setName] = useState("");
  const [type, setType] = useState<string>(ACTIVITY_TYPES[0]);
  const [status, setStatus] = useState<string>(ACTIVITY_STATUSES[0]);
  const [organizer, setOrganizer] = useState("");
  const [startDate, setStartDate] = useState(todayLocal());
  const [endDate, setEndDate] = useState(todayLocal());
  const [location, setLocation] = useState("");
  const [participants, setParticipants] = useState("");
  const [description, setDescription] = useState("");

  // 附件状态（对齐 Python：current_attachment_path / new_attachment_path / attachment_removed）
  const [currentAttachment, setCurrentAttachment] = useState<string | null>(null);
  const [newFile, setNewFile] = useState<string | null>(null);
  const [removed, setRemoved] = useState(false);

  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // 编辑模式：调后端 get_activity 回填（对齐 Python load_activity_data）
  useEffect(() => {
    if (!isEdit || editingId === undefined) return;
    (async () => {
      try {
        const detail = await invoke<AcademicActivity | null>("get_activity", {
          id: editingId,
        });
        if (!detail) {
          setError("未找到该活动记录，可能已被删除。");
          return;
        }
        setName(detail.name);
        setType(detail.type);
        setStatus(detail.status ?? ACTIVITY_STATUSES[0]);
        setOrganizer(detail.organizer ?? "");
        setStartDate(detail.start_date ?? todayLocal());
        setEndDate(detail.end_date ?? todayLocal());
        setLocation(detail.location ?? "");
        setParticipants(detail.participants ?? "");
        setDescription(detail.description ?? "");
        setCurrentAttachment(detail.attachment_path);
      } catch (err) {
        setError(String(err));
      } finally {
        setIsLoadingDetail(false);
      }
    })();
  }, [isEdit, editingId]);

  // 选择附件文件（对齐 Python ActivityDialog._select_file）
  const selectFile = async () => {
    try {
      const file = await open({
        multiple: false,
        title: "选择附件文件",
      });
      if (typeof file === "string") {
        setNewFile(file);
        setRemoved(false); // 选了新文件即不再标记移除
        setError(null);
      }
    } catch (err) {
      setError(String(err));
    }
  };

  // 移除附件（对齐 Python ActivityDialog._remove_selected_attachment）
  const removeAttachment = () => {
    if (newFile) {
      // 正在移除刚选的新文件
      setNewFile(null);
      if (currentAttachment) {
        setRemoved(false); // 还有原附件，仍可再次移除
      } else {
        setRemoved(true); // 原无附件 → 保持空
      }
    } else if (currentAttachment) {
      // 移除已保存的附件
      setRemoved(true);
      setNewFile(null);
    }
  };

  // 附件展示文本
  const attachmentLabel = () => {
    if (removed) return "无附件 (待移除)";
    if (newFile) return newFile.split(/[\\/]/).pop() ?? newFile;
    if (currentAttachment) return currentAttachment.split(/[\\/]/).pop() ?? currentAttachment;
    return "无附件";
  };

  // 移除按钮可用：有待移除的新文件或已有附件
  const canRemove = !!newFile || !!currentAttachment;
  // 选择按钮文案（对齐 Python：已有附件时点选表示「替换」）
  const selectBtnText = currentAttachment || newFile ? "重新选择/替换" : "选择文件";

  const computeAttachmentState = (): ActivityAttachmentState => {
    if (removed) {
      if (currentAttachment) return { action: "delete", oldPath: currentAttachment, newFile: null };
      return { action: "none", oldPath: null, newFile: null };
    }
    if (newFile) {
      if (currentAttachment && currentAttachment !== newFile) {
        return { action: "replace", oldPath: currentAttachment, newFile };
      }
      if (!currentAttachment) return { action: "add", oldPath: null, newFile };
    }
    // 未改动：编辑时保留原路径（old），新增时为空
    return { action: "none", oldPath: currentAttachment, newFile: null };
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    // 对齐 Python accept 校验：仅名称必填
    if (!name.trim()) {
      setError("活动名称不能为空");
      return;
    }

    const data: ActivityFormData = {
      name: name.trim(),
      type,
      status: status.trim() || null,
      organizer: organizer.trim() || null,
      start_date: startDate || null,
      end_date: endDate || null,
      location: location.trim() || null,
      participants: participants.trim() || null,
      description: description.trim() || null,
      attachment: computeAttachmentState(),
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
  const title = isEdit ? "编辑活动信息" : "新增活动信息";

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
          {isLoadingDetail && <div className="form-info">正在加载活动数据…</div>}

          <div className="form-group">
            <label htmlFor="activity-name">活动名称 *</label>
            <input
              id="activity-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="请输入活动名称，必填"
              disabled={isLoadingDetail}
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="activity-type">活动类型</label>
            <select
              id="activity-type"
              value={type}
              onChange={(e) => setType(e.target.value)}
              disabled={isLoadingDetail}
            >
              {ACTIVITY_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="activity-status">活动状态</label>
            <select
              id="activity-status"
              value={status}
              onChange={(e) => setStatus(e.target.value)}
              disabled={isLoadingDetail}
            >
              {ACTIVITY_STATUSES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="activity-organizer">主办方</label>
            <input
              id="activity-organizer"
              type="text"
              value={organizer}
              onChange={(e) => setOrganizer(e.target.value)}
              placeholder="请输入主办方"
              disabled={isLoadingDetail}
            />
          </div>

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="activity-start-date">开始日期</label>
              <input
                id="activity-start-date"
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                disabled={isLoadingDetail}
              />
            </div>
            <div className="form-group">
              <label htmlFor="activity-end-date">结束日期</label>
              <input
                id="activity-end-date"
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                disabled={isLoadingDetail}
              />
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="activity-location">活动地点</label>
            <input
              id="activity-location"
              type="text"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              placeholder="请输入活动地点"
              disabled={isLoadingDetail}
            />
          </div>

          <div className="form-group">
            <label htmlFor="activity-participants">参与人员</label>
            <textarea
              id="activity-participants"
              value={participants}
              onChange={(e) => setParticipants(e.target.value)}
              placeholder="请输入参与人员"
              rows={2}
              disabled={isLoadingDetail}
            />
          </div>

          <div className="form-group">
            <label htmlFor="activity-description">活动描述</label>
            <textarea
              id="activity-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="请输入活动描述"
              rows={3}
              disabled={isLoadingDetail}
            />
          </div>

          {/* 活动附件：选择 / 移除（Python ActivityDialog 自带，编辑也可改） */}
          <div className="form-group">
            <label>活动附件</label>
            <div className="form-row">
              <span className="file-path-label" style={{ flex: 1 }} title={attachmentLabel()}>
                {attachmentLabel()}
              </span>
              <button
                type="button"
                onClick={selectFile}
                disabled={isLoadingDetail}
                className="file-select-btn"
              >
                {selectBtnText}
              </button>
              <button
                type="button"
                onClick={removeAttachment}
                disabled={!canRemove || isLoadingDetail}
                className="file-select-btn danger"
              >
                移除附件
              </button>
            </div>
            {currentAttachment && !removed && !newFile && (
              <div className="hint" style={{ marginTop: 4, wordBreak: "break-all" }}>
                当前附件: {currentAttachment}
              </div>
            )}
            {newFile && (
              <div className="hint" style={{ marginTop: 4, wordBreak: "break-all" }}>
                已选: {newFile}
              </div>
            )}
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
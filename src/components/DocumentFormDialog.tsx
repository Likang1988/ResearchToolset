// 文档对话框：新增 / 编辑共用
// 对应 Python app/views/projecting_interface/project_document.py::DocumentDialog
// 校验与 Python accept 一致：名称必填；新增时必选要上传的文件。
// 新增时选中的文件（源路径）经 onSubmit 交回页面层做附件拷贝 + 入库。

import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { open } from "@tauri-apps/plugin-dialog";

// 全部文档类型（与后端 core::services::document::DOCUMENT_TYPES 一致）
export const DOCUMENT_TYPES = [
  "申请材料",
  "开题材料",
  "合同/任务书",
  "研究数据",
  "进展报告",
  "外协材料",
  "质量管理",
  "结题材料",
  "会议纪要",
  "其他",
];

// 页面层提交用的表单数据（file_path 为新增时用户选择的源文件路径）
export interface DocumentFormData {
  name: string;
  doc_type: string;
  version: string | null;
  description: string | null;
  keywords: string | null;
  file_path: string | null;
}

// 与后端 core::models::ProjectDocument 对齐（get_document 返回结构，编辑回填用）
interface ProjectDocument {
  id: number;
  project_id: number;
  name: string;
  doc_type: string;
  version: string | null;
  description: string | null;
  file_path: string | null;
  upload_time: string | null;
  keywords: string | null;
}

interface Props {
  editingId?: number;
  onSubmit: (data: DocumentFormData, id?: number) => Promise<void>;
  onClose: () => void;
}

export default function DocumentFormDialog({
  editingId,
  onSubmit,
  onClose,
}: Props) {
  const isEdit = editingId !== undefined;
  const [isLoadingDetail, setIsLoadingDetail] = useState(isEdit);
  const [name, setName] = useState("");
  const [docType, setDocType] = useState<string>(DOCUMENT_TYPES[0]);
  const [version, setVersion] = useState("");
  const [keywords, setKeywords] = useState("");
  const [description, setDescription] = useState("");
  // 新增模式：用户选择的源文件路径；编辑模式：已有附件的显示路径（只读）
  const [sourceFile, setSourceFile] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // 编辑模式：调后端 get_document 回填（对齐 Python load_document_data）
  useEffect(() => {
    if (!isEdit || editingId === undefined) return;
    (async () => {
      try {
        const detail = await invoke<ProjectDocument | null>("get_document", {
          id: editingId,
        });
        if (!detail) {
          setError("未找到该文档记录，可能已被删除。");
          return;
        }
        setName(detail.name);
        setDocType(detail.doc_type);
        setVersion(detail.version ?? "");
        setKeywords(detail.keywords ?? "");
        setDescription(detail.description ?? "");
        setSourceFile(detail.file_path);
      } catch (err) {
        setError(String(err));
      } finally {
        setIsLoadingDetail(false);
      }
    })();
  }, [isEdit, editingId]);

  // 选择要上传的文件（对齐 Python DocumentDialog.select_file）
  const selectFile = async () => {
    try {
      const file = await open({
        multiple: false,
        title: "选择文件",
      });
      if (typeof file === "string") {
        setSourceFile(file);
        setError(null);
      }
    } catch (err) {
      setError(String(err));
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    // 对齐 Python accept 校验
    if (!name.trim()) {
      setError("文档名称不能为空");
      return;
    }
    if (!isEdit && !sourceFile) {
      setError("请选择要上传的文件");
      return;
    }

    const data: DocumentFormData = {
      name: name.trim(),
      doc_type: docType,
      version: version.trim() || null,
      description: description.trim() || null,
      keywords: keywords.trim() || null,
      // 新增 → 源文件路径；编辑 → 不改附件（file_path 忽略，后端 update 不写）
      file_path: isEdit ? null : sourceFile,
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
  const title = isEdit ? "编辑文档信息" : "新增文档信息";

  return (
    <div className="dialog-overlay">
      <div className="dialog-container" style={{ width: 520 }}>
        <div className="dialog-header">
          <h2>{title}</h2>
          <button className="close-btn" onClick={() => !anyLoading && onClose()}>
            &times;
          </button>
        </div>
        <form onSubmit={handleSubmit} className="dialog-body">
          {error && <div className="form-error">{error}</div>}
          {isLoadingDetail && <div className="form-info">正在加载文档数据…</div>}

          <div className="form-group">
            <label htmlFor="doc-name">文档名称 *</label>
            <input
              id="doc-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="请输入文档名称，必填"
              disabled={isLoadingDetail}
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="doc-type">文档类型</label>
            <select
              id="doc-type"
              value={docType}
              onChange={(e) => setDocType(e.target.value)}
              disabled={isLoadingDetail}
            >
              {DOCUMENT_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="doc-version">版 本 号</label>
            <input
              id="doc-version"
              type="text"
              value={version}
              onChange={(e) => setVersion(e.target.value)}
              placeholder="请输入版本号"
              disabled={isLoadingDetail}
            />
          </div>

          <div className="form-group">
            <label htmlFor="doc-keywords">关 键 词</label>
            <input
              id="doc-keywords"
              type="text"
              value={keywords}
              onChange={(e) => setKeywords(e.target.value)}
              placeholder="请输入关键词（用逗号分隔）"
              disabled={isLoadingDetail}
            />
          </div>

          <div className="form-group">
            <label htmlFor="doc-description">文档描述</label>
            <textarea
              id="doc-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="请输入文档描述"
              rows={4}
              disabled={isLoadingDetail}
            />
          </div>

          <div className="form-group">
            <label>选择文件</label>
            {isEdit ? (
              <div className="hint" style={{ wordBreak: "break-all" }}>
                {sourceFile
                  ? `当前附件: ${sourceFile}`
                  : "当前无附件，可在列表中通过「上传附件」添加。"}
              </div>
            ) : (
              <div className="form-row">
                <button
                  type="button"
                  onClick={selectFile}
                  disabled={isLoadingDetail}
                  className="file-select-btn"
                >
                  {sourceFile ? "重新选择文件" : "选择文件"}
                </button>
                {sourceFile && (
                  <span className="file-path-label" title={sourceFile}>
                    {sourceFile.split(/[\\/]/).pop()}
                  </span>
                )}
              </div>
            )}
            {!isEdit && sourceFile && (
              <div className="hint" style={{ marginTop: 4, wordBreak: "break-all" }}>
                已选: {sourceFile}
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
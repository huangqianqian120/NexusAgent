import { useState, useEffect, useCallback, useRef } from 'react';
import {
  Code,
  Trash2,
  X,
  Loader2,
  Plus,
  Upload,
  FileArchive,
  CheckCircle,
  AlertCircle,
} from 'lucide-react';
import JSZip from 'jszip';
import { cn } from '../lib/utils';
import { listSkills, uploadSkill, deleteSkill, type Skill } from '../lib/api';

interface SkillsPanelProps {
  onClose: () => void;
}

interface ParsedSkill {
  name: string;
  description: string;
  content: string;
  filename: string;
}

export function SkillsPanel({ onClose }: SkillsPanelProps) {
  const [skills, setSkills] = useState<Skill[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [showUpload, setShowUpload] = useState(false);
  const [uploadForm, setUploadForm] = useState({ name: '', description: '', content: '' });
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [parsedSkills, setParsedSkills] = useState<ParsedSkill[]>([]);
  const [uploadProgress, setUploadProgress] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadSkills = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listSkills();
      setSkills(data);
    } catch (err) {
      console.error('Failed to load skills:', err);
      setError('加载技能失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSkills();
  }, [loadSkills]);

  const parseZipFile = async (file: File): Promise<ParsedSkill[]> => {
    const zip = new JSZip();
    const contents = await zip.loadAsync(file);
    const parsed: ParsedSkill[] = [];

    for (const [filename, zipEntry] of Object.entries(contents.files)) {
      if (zipEntry.dir || !filename.endsWith('.md')) continue;

      const content = await zipEntry.async('string');
      const skill = parseSkillContent(filename, content);
      if (skill) {
        parsed.push(skill);
      }
    }

    return parsed;
  };

  const parseSkillContent = (filename: string, content: string): ParsedSkill | null => {
    const skillMatch = content.match(/^#\s*Skill:\s*([^\n]+)/m);
    const descMatch = content.match(/^##\s*Description\s*\n(.+?)(?=\n##|\n#|$)/ms);
    const contentMatch = content.match(/^##\s*Content\s*\n([\s\S]+)$/m);

    let name = skillMatch?.[1]?.trim() || filename.replace(/\.md$/, '');
    let description = descMatch?.[1]?.trim() || '';
    let skillContent = contentMatch?.[1]?.trim() || content;

    if (!skillMatch) {
      name = filename.replace(/\.md$/, '').replace(/[^a-zA-Z0-9_-]/g, '-');
    }

    skillContent = skillContent.trim();
    if (!skillContent) return null;

    return { name, description, content: skillContent, filename };
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(false);
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(false);
    setError(null);

    const files = Array.from(e.dataTransfer.files);
    const zipFiles = files.filter(f => f.name.endsWith('.zip'));

    if (zipFiles.length === 0) {
      setError('请拖放 ZIP 文件');
      return;
    }

    const allParsed: ParsedSkill[] = [];
    for (const zipFile of zipFiles) {
      try {
        const parsed = await parseZipFile(zipFile);
        allParsed.push(...parsed);
      } catch (err) {
        setError(`解析 ${zipFile.name} 失败`);
        return;
      }
    }

    if (allParsed.length === 0) {
      setError('ZIP 中未找到 .md 文件');
      return;
    }

    setParsedSkills(allParsed);
  };

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    if (files.length === 0) return;

    const zipFiles = files.filter(f => f.name.endsWith('.zip'));
    if (zipFiles.length === 0) {
      setError('请选择 ZIP 文件');
      return;
    }

    const allParsed: ParsedSkill[] = [];
    for (const zipFile of zipFiles) {
      try {
        const parsed = await parseZipFile(zipFile);
        allParsed.push(...parsed);
      } catch (err) {
        setError(`解析 ${zipFile.name} 失败`);
        return;
      }
    }

    if (allParsed.length === 0) {
      setError('ZIP 中未找到 .md 文件');
      return;
    }

    setParsedSkills(allParsed);
    e.target.value = '';
  };

  const handleUploadSingle = async () => {
    if (!uploadForm.name.trim() || !uploadForm.content.trim()) {
      setError('名称和内容不能为空');
      return;
    }

    setUploading(true);
    setError(null);
    try {
      await uploadSkill(uploadForm);
      setUploadForm({ name: '', description: '', content: '' });
      setShowUpload(false);
      setParsedSkills([]);
      loadSkills();
    } catch (err) {
      setError('上传失败');
    } finally {
      setUploading(false);
    }
  };

  const handleUploadBatch = async () => {
    if (parsedSkills.length === 0) return;

    setUploading(true);
    setError(null);
    let successCount = 0;
    let failCount = 0;

    for (const skill of parsedSkills) {
      setUploadProgress(`上传 ${skill.name}...`);
      try {
        await uploadSkill({
          name: skill.name,
          description: skill.description,
          content: skill.content,
        });
        successCount++;
      } catch (err) {
        failCount++;
      }
    }

    setUploading(false);
    setUploadProgress(null);

    if (failCount > 0) {
      setError(`上传完成: ${successCount} 成功, ${failCount} 失败`);
    }

    setParsedSkills([]);
    setShowUpload(false);
    loadSkills();
  };

  const handleDelete = async (name: string) => {
    setDeleting(name);
    try {
      await deleteSkill(name);
      setSkills((prev) => prev.filter((s) => s.name !== name));
    } catch (err) {
      setError('删除失败');
    } finally {
      setDeleting(null);
    }
  };

  const openUpload = () => {
    setShowUpload(true);
    setParsedSkills([]);
    setUploadForm({ name: '', description: '', content: '' });
    setError(null);
  };

  const closeUpload = () => {
    setShowUpload(false);
    setParsedSkills([]);
    setError(null);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div
        className={cn(
          'w-full max-w-2xl mx-4 rounded-2xl border border-[hsl(240,3.7%,15.9%)]',
          'bg-[hsl(240,10%,3.9%)] overflow-hidden',
          'shadow-[0_0_40px_hsl(168,100%,50%)/0.1],0_25rem_3rem_rgba(0,0,0,0.5)'
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[hsl(240,3.7%,15.9%)]">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-[hsl(168,100%,50%)]/10 flex items-center justify-center">
              <Code className="w-5 h-5 text-[hsl(168,100%,50%)]" />
            </div>
            <div>
              <h2 className="font-semibold text-[hsl(0,0%,98%)]">Skills 技能管理</h2>
              <p className="text-xs text-[hsl(240,5%,64.9%)]">管理您的自定义技能</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-[hsl(240,3.7%,15.9%)] transition-colors"
          >
            <X className="w-5 h-5 text-[hsl(240,5%,64.9%)]" />
          </button>
        </div>

        {/* Content */}
        <div className="p-4 max-h-[60vh] overflow-y-auto">
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-6 h-6 text-[hsl(168,100%,50%)] animate-spin" />
            </div>
          ) : error && !showUpload ? (
            <div className="text-center py-8">
              <AlertCircle className="w-8 h-8 mx-auto mb-3 text-red-400" />
              <p className="text-red-400 text-sm mb-4">{error}</p>
              <button
                onClick={() => { setError(null); loadSkills(); }}
                className="px-4 py-2 rounded-lg bg-[hsl(240,3.7%,15.9%)] hover:bg-[hsl(240,3.7%,25.9%)] text-sm"
              >
                重试
              </button>
            </div>
          ) : showUpload ? (
            /* Upload Panel */
            <div className="space-y-4">
              {/* Drop Zone */}
              <div
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
                className={cn(
                  'flex flex-col items-center justify-center py-8 px-4 rounded-xl border-2 border-dashed transition-all cursor-pointer',
                  dragOver
                    ? 'border-[hsl(168,100%,50%)] bg-[hsl(168,100%,50%)]/5'
                    : 'border-[hsl(240,3.7%,15.9%)] hover:border-[hsl(168,100%,50%)]/30'
                )}
              >
                <Upload className={cn('w-8 h-8 mb-2', dragOver ? 'text-[hsl(168,100%,50%)]' : 'text-[hsl(240,5%,64.9%)]')} />
                <p className="text-sm text-[hsl(0,0%,98%)] mb-1">拖放 ZIP 文件到这里</p>
                <p className="text-xs text-[hsl(240,5%,64.9%)]">或点击选择文件</p>
                <p className="text-xs text-[hsl(240,5%,64.9%)] mt-2 opacity-60">ZIP 中包含的 .md 文件将被自动解析并批量上传</p>
              </div>

              {parsedSkills.length > 0 ? (
                /* Batch Preview */
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <FileArchive className="w-4 h-4 text-[hsl(168,100%,50%)]" />
                    <span className="text-sm font-medium text-[hsl(0,0%,98%)]">
                      批量上传 ({parsedSkills.length} 个技能)
                    </span>
                  </div>
                  <div className="max-h-40 overflow-y-auto space-y-2 mb-4">
                    {parsedSkills.map((skill, idx) => (
                      <div key={idx} className="flex items-start gap-3 p-3 rounded-lg bg-[hsl(240,3.7%,15.9%)]/50 border border-[hsl(240,3.7%,15.9%)]">
                        <CheckCircle className="w-4 h-4 text-green-400 mt-0.5 flex-shrink-0" />
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-[hsl(0,0%,98%)]">{skill.name}</p>
                          <p className="text-xs text-[hsl(240,5%,64.9%)] mt-0.5">{skill.description || skill.filename}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                /* Manual Form */
                <div className="space-y-3">
                  <div>
                    <label className="block text-xs text-[hsl(240,5%,64.9%)] mb-1">技能名称</label>
                    <input
                      type="text"
                      value={uploadForm.name}
                      onChange={(e) => setUploadForm({ ...uploadForm, name: e.target.value })}
                      placeholder="my-skill"
                      className="w-full px-3 py-2 rounded-lg bg-[hsl(240,3.7%,15.9%)] border border-[hsl(240,3.7%,25.9%)] text-sm text-[hsl(0,0%,98%)] placeholder:text-[hsl(240,5%,64.9%)] focus:outline-none focus:border-[hsl(168,100%,50%)]/50"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-[hsl(240,5%,64.9%)] mb-1">描述</label>
                    <input
                      type="text"
                      value={uploadForm.description}
                      onChange={(e) => setUploadForm({ ...uploadForm, description: e.target.value })}
                      placeholder="这个技能做什么"
                      className="w-full px-3 py-2 rounded-lg bg-[hsl(240,3.7%,15.9%)] border border-[hsl(240,3.7%,25.9%)] text-sm text-[hsl(0,0%,98%)] placeholder:text-[hsl(240,5%,64.9%)] focus:outline-none focus:border-[hsl(168,100%,50%)]/50"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-[hsl(240,5%,64.9%)] mb-1">内容</label>
                    <textarea
                      value={uploadForm.content}
                      onChange={(e) => setUploadForm({ ...uploadForm, content: e.target.value })}
                      placeholder="技能的指令内容..."
                      rows={6}
                      className="w-full px-3 py-2 rounded-lg bg-[hsl(240,3.7%,15.9%)] border border-[hsl(240,3.7%,25.9%)] text-sm text-[hsl(0,0%,98%)] placeholder:text-[hsl(240,5%,64.9%)] focus:outline-none focus:border-[hsl(168,100%,50%)]/50 resize-none"
                    />
                  </div>
                </div>
              )}

              {error && (
                <p className="text-xs text-red-400">{error}</p>
              )}

              {/* Actions */}
              <div className="flex gap-2 pt-2">
                <button
                  onClick={closeUpload}
                  className="flex-1 px-4 py-2 rounded-lg border border-[hsl(240,3.7%,15.9%)] hover:bg-[hsl(240,3.7%,15.9%)] text-sm transition-colors"
                >
                  取消
                </button>
                {parsedSkills.length > 0 ? (
                  <button
                    onClick={handleUploadBatch}
                    disabled={uploading}
                    className="flex-1 px-4 py-2 rounded-lg bg-gradient-to-r from-[hsl(168,100%,50%)] to-[hsl(187,100%,50%)] text-[hsl(240,10%,3.9%)] font-medium text-sm disabled:opacity-50 transition-all flex items-center justify-center gap-2"
                  >
                    {uploading ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        {uploadProgress || '上传中...'}
                      </>
                    ) : (
                      '全部上传'
                    )}
                  </button>
                ) : (
                  <button
                    onClick={handleUploadSingle}
                    disabled={uploading || !uploadForm.name.trim() || !uploadForm.content.trim()}
                    className="flex-1 px-4 py-2 rounded-lg bg-gradient-to-r from-[hsl(168,100%,50%)] to-[hsl(187,100%,50%)] text-[hsl(240,10%,3.9%)] font-medium text-sm disabled:opacity-50 transition-all"
                  >
                    {uploading ? <Loader2 className="w-4 h-4 mx-auto animate-spin" /> : '上传'}
                  </button>
                )}
              </div>
            </div>
          ) : (
            /* Skills List */
            <div className="space-y-2">
              {skills.length === 0 ? (
                <div className="text-center py-8 text-[hsl(240,5%,64.9%)] text-sm">
                  暂无自定义技能，点击下方按钮上传
                </div>
              ) : (
                skills.map((skill) => (
                  <div
                    key={skill.name}
                    className="flex items-start gap-3 p-4 rounded-xl bg-[hsl(240,3.7%,15.9%)]/50 border border-[hsl(240,3.7%,15.9%)] hover:border-[hsl(168,100%,50%)]/30 transition-all"
                  >
                    <div className="w-8 h-8 rounded-lg bg-[hsl(168,100%,50%)]/10 flex items-center justify-center flex-shrink-0">
                      <Code className="w-4 h-4 text-[hsl(168,100%,50%)]" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="text-sm font-medium text-[hsl(0,0%,98%)]">{skill.name}</p>
                        {skill.source === 'bundled' && (
                          <span className="px-1.5 py-0.5 rounded text-[10px] bg-[hsl(240,3.7%,25.9%)] text-[hsl(240,5%,64.9%)]">内置</span>
                        )}
                      </div>
                      <p className="text-xs text-[hsl(240,5%,64.9%)] mt-0.5">{skill.description || '无描述'}</p>
                      {skill.source !== 'bundled' && (
                        <p className="text-xs text-[hsl(240,5%,64.9%)] mt-1 opacity-60">来源: {skill.source}</p>
                      )}
                    </div>
                    {skill.source !== 'bundled' && (
                      <button
                        onClick={() => handleDelete(skill.name)}
                        disabled={deleting === skill.name}
                        className="p-2 rounded-lg hover:bg-red-500/10 text-[hsl(240,5%,64.9%)] hover:text-red-400 transition-colors"
                      >
                        {deleting === skill.name ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <Trash2 className="w-4 h-4" />
                        )}
                      </button>
                    )}
                  </div>
                ))
              )}
            </div>
          )}
        </div>

        {/* Hidden file input */}
        <input
          ref={fileInputRef}
          type="file"
          accept=".zip"
          multiple
          onChange={handleFileSelect}
          className="hidden"
        />

        {/* Footer */}
        {!showUpload && (
          <div className="px-4 py-3 border-t border-[hsl(240,3.7%,15.9%)] bg-[hsl(240,10%,3.9%)]/50">
            <button
              onClick={openUpload}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-[hsl(168,100%,50%)] to-[hsl(187,100%,50%)] text-[hsl(240,10%,3.9%)] font-medium text-sm hover:shadow-[0_0_20px_hsl(168,100%,50%)/0.4] transition-all"
            >
              <Plus className="w-4 h-4" />
              上传新技能
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

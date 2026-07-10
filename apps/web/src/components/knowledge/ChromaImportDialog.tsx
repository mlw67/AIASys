/**
 * Chroma 向量数据库导入弹窗
 *
 * 用于从 Chroma 原生磁盘存储导入数据到 AIASys 知识库，
 * 直接复用 Chroma 中已有的向量，不重新调用 embedding API。
 */

import { Database, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { LLMModelConfig } from "@/lib/api/llm";
import type { ChromaImportResponse, ChromaImportResult } from "@/types/knowledge";

export interface ChromaImportDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  chromaPersistDir: string;
  onChromaPersistDirChange: (value: string) => void;
  chromaCollectionName: string;
  onChromaCollectionNameChange: (value: string) => void;
  importAllCollections: boolean;
  onImportAllCollectionsChange: (value: boolean) => void;
  chromaDocumentSourceKey: string;
  onChromaDocumentSourceKeyChange: (value: string) => void;
  chromaEmbeddingModel: string;
  onChromaEmbeddingModelChange: (value: string) => void;
  embeddingModels: LLMModelConfig[];
  isLoadingModels: boolean;
  importResults: ChromaImportResponse | null;
  isImporting: boolean;
  onImport: () => void;
}

function formatEmbeddingModel(model: LLMModelConfig): string {
  const dimension = typeof model.dimension === "number" ? ` · ${model.dimension}维` : "";
  const disabledLabel = model.enabled === false ? "（已禁用）" : "";
  return `${model.name || model.model}${dimension}${disabledLabel}`;
}

export function ChromaImportDialog({
  open,
  onOpenChange,
  chromaPersistDir,
  onChromaPersistDirChange,
  chromaCollectionName,
  onChromaCollectionNameChange,
  importAllCollections,
  onImportAllCollectionsChange,
  chromaDocumentSourceKey,
  onChromaDocumentSourceKeyChange,
  chromaEmbeddingModel,
  onChromaEmbeddingModelChange,
  embeddingModels,
  isLoadingModels,
  importResults,
  isImporting,
  onImport,
}: ChromaImportDialogProps) {
  const hasResults = importResults !== null;
  const allSucceeded = importResults?.success ?? false;
  const collectionInputDisabled = isImporting || importAllCollections;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex h-[90vh] flex-col overflow-hidden p-0 sm:max-w-[620px]">
        <DialogHeader className="shrink-0 px-6 pt-6">
          <DialogTitle className="flex items-center gap-2">
            <Database className="h-5 w-5" />
            从 Chroma 导入
          </DialogTitle>
          <DialogDescription>
            读取 Chroma 原生磁盘存储，直接复用已有的向量数据，不重新调用 embedding API。
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 min-h-0 space-y-5 overflow-y-auto px-6 py-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">Chroma 持久化目录</label>
            <Input
              placeholder="例如 C:/path/to/chroma_data"
              value={chromaPersistDir}
              onChange={(e) => onChromaPersistDirChange(e.target.value)}
              disabled={isImporting}
            />
            <p className="text-xs leading-5 text-muted-foreground">
              该目录下需包含 chroma.sqlite3 文件。
            </p>
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-sm font-medium">Collection 名称</label>
              <label className="flex items-center gap-2 text-xs text-muted-foreground">
                <input
                  type="checkbox"
                  className="h-3.5 w-3.5 rounded border-border"
                  checked={importAllCollections}
                  onChange={(e) => onImportAllCollectionsChange(e.target.checked)}
                  disabled={isImporting}
                />
                导入全部 collection
              </label>
            </div>
            <Input
              placeholder={importAllCollections ? "留空表示导入所有 collection" : "例如 default"}
              value={chromaCollectionName}
              onChange={(e) => onChromaCollectionNameChange(e.target.value)}
              disabled={collectionInputDisabled}
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">Source 字段名</label>
            <Input
              placeholder="默认 source"
              value={chromaDocumentSourceKey}
              onChange={(e) => onChromaDocumentSourceKeyChange(e.target.value)}
              disabled={isImporting}
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">Embedding 模型</label>
            <Select
              value={chromaEmbeddingModel || "__default__"}
              onValueChange={(value) => {
                onChromaEmbeddingModelChange(value === "__default__" ? "" : value);
              }}
              disabled={isImporting}
            >
              <SelectTrigger>
                <SelectValue placeholder="选择原始向量对应的 embedding 模型" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__default__">跟随默认 embedding</SelectItem>
                {embeddingModels.map((model) => (
                  <SelectItem key={model.id} value={model.id}>
                    {formatEmbeddingModel(model)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs leading-5 text-muted-foreground">
              必须与生成 Chroma 原始向量时使用的模型一致，且维度相同。
            </p>
            {isLoadingModels ? (
              <p className="text-xs leading-5 text-muted-foreground">正在读取模型配置…</p>
            ) : embeddingModels.length === 0 ? (
              <p className="text-xs leading-5 text-muted-foreground">
                当前未配置 embedding 模型，可先到设置中完成配置。
              </p>
            ) : null}
          </div>

          {hasResults ? (
            <div className="space-y-3 rounded-xl border border-border bg-muted/40 p-4">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">导入结果</span>
                <span
                  className={`text-xs ${
                    allSucceeded ? "text-green-600" : "text-amber-600"
                  }`}
                >
                  {importResults.imported_documents}/{importResults.total_documents} 个文档成功
                </span>
              </div>
              <div className="max-h-56 space-y-2 overflow-y-auto">
                {importResults.results.map((result: ChromaImportResult, idx: number) => (
                  <div
                    key={`chroma-result-${idx}`}
                    className="flex items-start justify-between rounded-lg border border-border bg-white p-3 text-sm"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span
                          className={`h-2 w-2 rounded-full ${
                            result.success ? "bg-green-500" : "bg-red-500"
                          }`}
                        />
                        <span className="truncate font-medium">{result.filename}</span>
                      </div>
                      {result.collection_name ? (
                        <p className="mt-0.5 text-xs text-muted-foreground">
                          collection: {result.collection_name}
                        </p>
                      ) : null}
                      {!result.success && (
                        <p className="mt-1 text-xs text-red-600">{result.message}</p>
                      )}
                    </div>
                    <span className="ml-3 whitespace-nowrap text-xs text-muted-foreground">
                      {result.chunk_count} chunks
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </div>

        <DialogFooter className="shrink-0 px-6 py-4">
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={isImporting}
          >
            关闭
          </Button>
          <Button
            onClick={() => void onImport()}
            disabled={
              isImporting ||
              !chromaPersistDir.trim() ||
              (!importAllCollections && !chromaCollectionName.trim()) ||
              !chromaEmbeddingModel
            }
          >
            {isImporting ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Database className="mr-2 h-4 w-4" />
            )}
            开始导入
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

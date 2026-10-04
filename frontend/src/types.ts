export type Column = { name:string; dtype:string; semantic_type:string; null_count:number; null_percentage:number; unique_count:number; examples:unknown[]; mean?:number|null; min?:number|null; max?:number|null };
export type Dataset = { id:string; project_id:string; filename:string; profile:{ row_count:number; column_count:number; duplicate_rows:number; memory_bytes:number; missing_cells:number; columns:Column[]; preview:Record<string,unknown>[] } };
export type Project = { id:string; name:string; description:string|null; created_at:string; datasets:Dataset[] };
export type Visualization = {type:'bar'|'line'|'scatter'|'histogram'|'box'|'pie';title:string;x?:string|null;y?:string|null;data:Record<string,unknown>[]};
export type Analysis = { conversation_id:string; answer:string; summary:string; analysis_type:string; code?:string|null; result:unknown; visualization?:Visualization|null; warnings:string[]; insights:string[] };

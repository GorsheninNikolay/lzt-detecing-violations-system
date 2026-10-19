import { useEffect, useRef, useState } from 'react'
import { accountRequest, apiAssetUrl } from './AccountShell'

type Annotation = { label: string; box: number[] }
type Example = { title: string; found: string; expected: string; check: string; outcome: string; photos: string[]; annotations?: Annotation[]; corrections?: {photo:string;original_annotations:Annotation[];corrected_annotations:Annotation[];comment:string;illustrative:boolean}[]; signals?: {kind:string;state:string;comment:string}[] }
export default function TrialExamples({ projectId, readOnly, rerun }: { projectId:string;readOnly:boolean;rerun:(files:File[])=>void }) {
  const [examples,setExamples]=useState<Example[]>([]), [error,setError]=useState(''), [busy,setBusy]=useState(false)
  const scope=useRef({projectId,generation:0})
  if(scope.current.projectId!==projectId)scope.current={projectId,generation:scope.current.generation+1}
  useEffect(()=>{
    const generation=scope.current.generation;setExamples([]);setError('');setBusy(false)
    void accountRequest(`/projects/${projectId}/trial`).then(data=>{if(generation===scope.current.generation)setExamples(data.examples??[])}).catch(()=>{if(generation===scope.current.generation)setExamples([])})
    return()=>{scope.current.generation++}
  },[projectId])
  async function load(example:Example){
    const generation=scope.current.generation;setBusy(true);setError('')
    try{const files=await Promise.all(example.photos.map(async(url,index)=>{const response=await fetch(apiAssetUrl(url),{credentials:'same-origin'});if(!response.ok)throw new Error('Не удалось загрузить учебные фотографии.');const blob=await response.blob();return new File([blob],`Учебный пример ${index+1}.${blob.type==='image/png'?'png':'jpg'}`,{type:blob.type})}));if(generation===scope.current.generation)rerun(files)}catch(reason){if(generation===scope.current.generation)setError((reason as Error).message)}finally{if(generation===scope.current.generation)setBusy(false)}
  }
  if(!examples.length)return null
  return <section className="panel"><h2>Учебные материалы проекта</h2><p>Иллюстративные результаты и разметка. Повтор загружает фотографии в обычную форму; запуск анализа требует отдельного согласия.</p>{error&&<p role="alert">{error}</p>}{examples.map((example,index)=><article key={index}><h3>{example.title}</h3><p>Найдено: {example.found}. Ожидалось: {example.expected}.</p><p>Проверка: {example.check}. Итог: {example.outcome}.</p><div className="example-photos">{example.photos.map(url=><a href={apiAssetUrl(url)} key={url} download><img src={apiAssetUrl(url)} alt={example.title} loading="lazy" /></a>)}</div>{example.annotations?.length ? <details><summary>Исходная учебная разметка</summary><AnnotationList items={example.annotations} /></details>:null}{example.corrections?.map((correction,index)=><section key={index}><h4>Иллюстративная правка человеком</h4><a href={apiAssetUrl(correction.photo)}>Исходная фотография</a><h5>Разметка до правки</h5><AnnotationList items={correction.original_annotations} /><h5>Разметка после правки человеком</h5><AnnotationList items={correction.corrected_annotations} /><p>{correction.comment}</p><p>Учебная правка показана отдельно и не изменяет исходные наблюдения.</p></section>)}{example.signals?.map((item,index)=><p key={index}>Учебный сигнал: {item.kind} · {item.state} · {item.comment}</p>)}<button disabled={readOnly||busy} onClick={()=>void load(example)}>Загрузить фото для нового анализа</button></article>)}</section>
}
function AnnotationList({items}:{items:Annotation[]}){return <ul>{items.map((item,index)=><li key={index}>{item.label} · область {item.box.join(', ')}</li>)}</ul>}

import { useEffect, useState } from 'react'

export default function FramePreview({ file, ordinal }: { file: File; ordinal: number }) {
  const [url, setUrl] = useState<string | null>(null)

  useEffect(() => {
    if (typeof URL.createObjectURL !== 'function') return
    const objectUrl = URL.createObjectURL(file)
    setUrl(objectUrl)
    return () => URL.revokeObjectURL(objectUrl)
  }, [file])

  return url ? <img className="frame-preview" src={url} alt={`Предпросмотр: кадр ${ordinal}, ${file.name}`} /> : null
}

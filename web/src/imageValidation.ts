const MAX_BYTES = 16_000_000
const MAX_PIXELS = 40_000_000

export function readFile(file: Blob): Promise<ArrayBuffer> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result as ArrayBuffer)
    reader.onerror = () => reject(reader.error)
    reader.readAsArrayBuffer(file)
  })
}

export async function validateImage(file: File): Promise<string | null> {
  const isJpeg =
    /\.jpe?g$/i.test(file.name) && (!file.type || file.type === 'image/jpeg')
  const isPng =
    /\.png$/i.test(file.name) && (!file.type || file.type === 'image/png')
  if (!isJpeg && !isPng)
    return 'Поддерживаются файлы JPEG (.jpg, .jpeg) и PNG (.png).'
  if (!file.size || file.size > MAX_BYTES)
    return 'Размер одного файла не должен превышать 16 МБ.'
  try {
    const bytes = new Uint8Array(await readFile(file.slice(0, 8)))
    if (
      isJpeg
        ? bytes[0] !== 0xff || bytes[1] !== 0xd8 || bytes[2] !== 0xff
        : bytes.some(
            (value, index) =>
              value !== [137, 80, 78, 71, 13, 10, 26, 10][index],
          )
    )
      return 'Файл не удалось прочитать как изображение.'
    const bitmap = await createImageBitmap(file)
    const pixels = bitmap.width * bitmap.height
    bitmap.close()
    if (pixels > MAX_PIXELS)
      return 'Изображение превышает 40 миллионов пикселей.'
  } catch {
    return 'Файл не удалось прочитать как изображение.'
  }
  return null
}

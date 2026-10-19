import { resolve } from 'node:path'
import { existsSync, readFileSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { inflateRawSync } from 'node:zlib'

const root=resolve(process.cwd(), existsSync(resolve(process.cwd(),'shared/trial-project')) ? 'shared/trial-project' : '../shared/trial-project')
export function trialFixture(){return JSON.parse(readFileSync(resolve(root,'manifest.json'),'utf8'))}
export function trialPhoto(name:string){if(!['excavation.jpg','overview.jpg'].includes(name))throw new Error('photo_not_found');return readFileSync(resolve(root,`photos/${name}`))}
function crc32(bytes:Uint8Array){let crc=0xffffffff;for(const value of bytes){crc^=value;for(let bit=0;bit<8;bit++)crc=(crc>>>1)^((crc&1)?0xedb88320:0)}return (crc^0xffffffff)>>>0}
export function trialZip(photosOnly=false){
  const manifest=trialFixture(),entries: [string,Buffer][]=[...Object.keys(manifest.files).map(name=>[name,trialPhoto(name.split('/').pop()!)] as [string,Buffer])]
  if(!photosOnly)entries.unshift(['manifest.json',Buffer.from(JSON.stringify(manifest))])
  let offset=0;const locals:Buffer[]=[],directory:Buffer[]=[]
  for(const [name,bytes]of entries){const filename=Buffer.from(name),crc=crc32(bytes),local=Buffer.alloc(30),central=Buffer.alloc(46);local.writeUInt32LE(0x04034b50,0);local.writeUInt16LE(20,4);local.writeUInt32LE(crc,14);local.writeUInt32LE(bytes.length,18);local.writeUInt32LE(bytes.length,22);local.writeUInt16LE(filename.length,26);central.writeUInt32LE(0x02014b50,0);central.writeUInt16LE(20,4);central.writeUInt16LE(20,6);central.writeUInt32LE(crc,16);central.writeUInt32LE(bytes.length,20);central.writeUInt32LE(bytes.length,24);central.writeUInt16LE(filename.length,28);central.writeUInt32LE(offset,42);locals.push(local,filename,bytes);directory.push(central,filename);offset+=local.length+filename.length+bytes.length}
  const center=Buffer.concat(directory),end=Buffer.alloc(22);end.writeUInt32LE(0x06054b50,0);end.writeUInt16LE(entries.length,8);end.writeUInt16LE(entries.length,10);end.writeUInt32LE(center.length,12);end.writeUInt32LE(offset,16);return Buffer.concat([...locals,center,end])
}
export function validateTrialZip(bytes:Buffer){
  if(bytes.length>20_000_000)throw new Error('archive_too_large')
  const files=new Map<string,Buffer>();let offset=0,total=0
  while(offset+30<=bytes.length&&bytes.readUInt32LE(offset)===0x04034b50){
    const flags=bytes.readUInt16LE(offset+6),method=bytes.readUInt16LE(offset+8),length=bytes.readUInt32LE(offset+18),plain=bytes.readUInt32LE(offset+22),nameLength=bytes.readUInt16LE(offset+26),extra=bytes.readUInt16LE(offset+28),name=bytes.subarray(offset+30,offset+30+nameLength).toString(),start=offset+30+nameLength+extra
    if(flags&9||!['manifest.json','photos/excavation.jpg','photos/overview.jpg'].includes(name)||files.has(name)||plain>10_000_000||start+length>bytes.length)throw new Error('invalid_archive')
    const packed=bytes.subarray(start,start+length),data=method===0?packed:method===8?inflateRawSync(packed,{maxOutputLength:10_000_000}):null
    if(!data||data.length!==plain||crc32(data)!==bytes.readUInt32LE(offset+14))throw new Error('invalid_archive')
    total+=data.length;if(total>20_000_000)throw new Error('archive_too_large');files.set(name,data);offset=start+length
  }
  const manifest=JSON.parse(files.get('manifest.json')?.toString()??'null'),expected=trialFixture()
  if(!manifest||manifest.schema_version!==1||JSON.stringify(manifest)!==JSON.stringify(expected)||files.size!==Object.keys(expected.files).length+1)throw new Error('unsupported_demo_archive')
  for(const [name,hash]of Object.entries(expected.files))if(createHash('sha256').update(files.get(name)??'').digest('hex')!==hash)throw new Error('archive_integrity')
  return manifest
}

import { useState } from 'react'
import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import WorkCatalogDialog from './WorkCatalogDialog'
import PlanEquipment from './PlanEquipment'

afterEach(() => { cleanup();vi.restoreAllMocks() })
it('searches work names or codes and chooses stable source identity without ordered markers',()=>{
 const choose=vi.fn()
 const works=[{id:'one',title:'Подготовка',code:'10.',source_row:4},{id:'two',title:'Вынос сетей',code:null,source_row:10},{id:'three',title:'Вынос сетей',code:null,source_row:11}]
 const {container}=render(<WorkCatalogDialog works={works} choose={choose} close={vi.fn()}/>)
 expect(container.querySelector('ol')).toBeNull()
 fireEvent.change(screen.getByLabelText('Найти по названию или коду'),{target:{value:'сете'}})
 expect(screen.getAllByRole('button',{name:/^Выбрать:/})).toHaveLength(2)
 fireEvent.click(screen.getByRole('button',{name:'Выбрать: Вынос сетей, строка 11'}))
 expect(choose).toHaveBeenCalledWith(works[2])
 fireEvent.change(screen.getByLabelText('Найти по названию или коду'),{target:{value:'10.'}})
 expect(screen.getByRole('button',{name:'Выбрать: Подготовка (10.)'})).toBeTruthy()
})
it('adds equipment once and changes its meaning without contradictory groups',()=>{
 const change=vi.fn()
 function Editor(){const [value,setValue]=useState({expected_equipment:[] as string[],allowed_equipment:['custom_machine'],excluded_equipment:[] as string[]});return <PlanEquipment value={value} ordinal={1} change={next=>{change(next);setValue(next)}}/>}
 render(<Editor/>);fireEvent.click(screen.getByRole('button',{name:'Добавить технику'}));fireEvent.click(screen.getByRole('button',{name:'Добавить: Экскаватор'}))
 expect(change).toHaveBeenLastCalledWith({expected_equipment:['excavator'],allowed_equipment:['custom_machine'],excluded_equipment:[]})
 expect(screen.queryByRole('button',{name:'Добавить: Экскаватор'})).toBeNull()
 fireEvent.change(screen.getByLabelText('Условие для Экскаватор · работа 1'),{target:{value:'excluded'}})
 expect(change).toHaveBeenLastCalledWith({expected_equipment:[],allowed_equipment:['custom_machine'],excluded_equipment:['excavator']})
 fireEvent.click(screen.getByRole('button',{name:'Убрать Экскаватор из работы 1'}))
 expect(change).toHaveBeenLastCalledWith({expected_equipment:[],allowed_equipment:['custom_machine'],excluded_equipment:[]})
})
it('preserves existing combined expectations until the user explicitly edits them',()=>{
 const change=vi.fn()
 render(<PlanEquipment value={{expected_equipment:['excavator'],allowed_equipment:['excavator'],excluded_equipment:['truck']}} ordinal={1} change={change}/>)
 expect(change).not.toHaveBeenCalled()
 const field=screen.getByLabelText('Условие для Экскаватор · работа 1') as HTMLSelectElement
 expect(field.value).toBe('expected_allowed')
 fireEvent.change(field,{target:{value:'expected'}})
 expect(change).toHaveBeenCalledWith({expected_equipment:['excavator'],allowed_equipment:[],excluded_equipment:['truck']})
 expect(within(screen.getByLabelText('Техника работы 1')).getByText('Грузовик')).toBeTruthy()
})

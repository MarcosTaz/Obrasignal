import {parseIsoDate} from './utils.mjs';
function addCalendarDays(date,days){const d=new Date(`${date}T00:00:00Z`);d.setUTCDate(d.getUTCDate()+days);return d.toISOString().slice(0,10);}
export function evaluateNoticeDeadline(contract,{eventDates={},asOf}){
  const today=parseIsoDate(asOf);const rule=contract?.rules?.noticeDeadline;
  if(!rule)return {state:'UNKNOWN',reason:'NOTICE_DEADLINE_RULE_MISSING',deadlineDate:null};
  const anchor=eventDates[rule.event];if(!anchor)return {state:'UNKNOWN',reason:'DEADLINE_EVENT_DATE_MISSING',event:rule.event,deadlineDate:null};
  parseIsoDate(anchor);const unit=String(rule.unit||'').toLowerCase();
  if(rule.dayType==='BUSINESS')return {state:'UNKNOWN',reason:'BUSINESS_CALENDAR_REQUIRED',event:rule.event,anchorDate:anchor,deadlineDate:null};
  if(rule.dayType!=='CALENDAR')return {state:'UNKNOWN',reason:'DAY_TYPE_UNRESOLVED',event:rule.event,anchorDate:anchor,deadlineDate:null};
  if(!/^(calendar )?days?$/.test(unit))return {state:'UNKNOWN',reason:'DEADLINE_UNIT_NOT_IMPLEMENTED',event:rule.event,anchorDate:anchor,deadlineDate:null};
  const due=addCalendarDays(anchor,rule.quantity);const state=today<due?'OPEN':today===due?'DUE_TODAY':'PASSED';
  return {state,reason:null,event:rule.event,anchorDate:anchor,deadlineDate:due,asOf:today,interpretation:'NOTICE_WINDOW_CANDIDATE_ONLY'};
}

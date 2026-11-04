/* Display-only FX. Original amounts stay integer IRR; decimal rates are exact rationals. */
"use strict";
const MazMoney=(()=>{
 function view(unit,settings={},currencies=[]){
  if(Array.isArray(settings))settings=Object.fromEntries(settings.map(x=>[x.key,x.value]));
  const selected=unit==='AUTO'?String(settings.report_currency||'IRR'):unit;
  const c=currencies.find(x=>x.id===selected||x.name===selected);
  if(['IRR','ریال'].includes(selected))return {name:'ریال',rate:'1',digits:0};
  if(['IRT','تومان'].includes(selected))return {name:'تومان',rate:'10',digits:1};
  const n=Number(settings.display_decimals??2),digits=Number.isInteger(n)&&n>=0&&n<=8?n:2;
  return {name:c?.name||selected,rate:String(c?.rial_per_unit||''),digits};
 }
 function format(value,unit,settings,currencies){
  const c=view(unit,settings,currencies),m=c.rate.match(/^(\d+)(?:\.(\d{1,8}))?$/);
  if(!m)return '— (نرخ ثبت نشده)';
  const fraction=m[2]||'',den=BigInt(m[1]+fraction),rateScale=10n**BigInt(fraction.length);
  if(!den)return '— (نرخ نامعتبر)';
  try{
   let n=BigInt(value||0),negative=n<0n;if(negative)n=-n;
   const scale=10n**BigInt(c.digits),numerator=n*rateScale*scale;
   let rounded=numerator/den;if((numerator%den)*2n>=den)rounded++;
   const f=new Intl.NumberFormat('fa-IR',{useGrouping:false});
   return (negative&&rounded?'−':'')+new Intl.NumberFormat('fa-IR').format(rounded/scale)+(c.digits?'٫'+f.format(rounded%scale).padStart(c.digits,'۰'):'');
  }catch{return '—';}
 }
 function units(currencies=[]){return [...new Set(['AUTO','IRR','IRT',...currencies.filter(x=>x.name).map(x=>x.id||x.name)])];}
 return {view,format,units};
})();
if(typeof module!=='undefined')module.exports=MazMoney;

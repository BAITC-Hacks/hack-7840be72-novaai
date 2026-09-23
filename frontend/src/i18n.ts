import dictionary from './translations.json';
export type Locale='kk'|'ru'|'en';
let locale:Locale='ru';
export function setLocale(value:Locale){locale=value;document.documentElement.lang=value;localStorage.setItem('cq-language',value);}
// Translate only rendered strings; objects, numbers and React elements are untouched.
export function tr(value:any):any{
 if(typeof value!=='string'||locale==='ru')return value;
 const key=value.trim();const translated=(dictionary as any)[key]?.[locale];
 return translated?value.replace(key,translated):value;
}

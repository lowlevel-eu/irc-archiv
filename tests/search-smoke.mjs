import {readFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {pathToFileURL, fileURLToPath} from 'node:url';
const site=fileURLToPath(new URL('../site/', import.meta.url)).replace(/\/$/,'');
globalThis.fetch=async(input)=>{
 const url=new URL(typeof input==='string'?input:input.url??input.toString(),'http://localhost');
 const file=resolve(site,url.pathname.replace(/^\/irc-archive\//,''));
 if(!file.startsWith(site+'/'))throw Error('Unexpected fetch '+file);
 const data=await readFile(file);
 return new Response(data,{headers:{'Content-Type':file.endsWith('.wasm')?'application/wasm':'application/octet-stream'}});
};
const module=await import(pathToFileURL(site+'/pagefind/pagefind.js'));
const api=module.createInstance({basePath:'/irc-archive/pagefind/',baseUrl:'/irc-archive/'});
const filters=await api.filters();
if(!filters.Kanal?.['#lost']||!filters.Kanal?.['#tyndur'])throw Error('Missing channel filters');
for(const [term,options] of [['Mikrokernel',{}],['kwolf',{filters:{Kanal:'#tyndur',Jahr:'2010'}}],['RECOVERY',{}]]){
 const results=await api.search(term,options);
 if(!results.results.length)throw Error('No results for '+term);
 const first=await results.results[0].data();
 if(!first.url.startsWith('/irc-archive/'))throw Error('Wrong URL prefix '+first.url);
 const url=new URL(first.url,'http://localhost');
 const html=await readFile(site+url.pathname.replace(/^\/irc-archive/,''),'utf8');
 if(!html.includes('id="'+url.hash.slice(1)+'"'))throw Error('Missing anchor '+first.url);
 if(options.filters&&(!first.filters.Kanal.includes('#tyndur')||!first.filters.Jahr.includes('2010')))throw Error('Filters not applied');
 console.log(JSON.stringify({term,matches:results.results.length,first:first.url,filters:first.filters}));
}
await api.destroy();

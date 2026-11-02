// Keyless YouTube pulls from a youtube.com tab (innertube, the page's own API key and client context).
// Paste into the console of any https://www.youtube.com page (or run it with a browser tool), then use:
//
//   await __playlistFull(pid)                 playlist header + every item in order ({id,title,len,idx,ch,chid,info})
//   await __channelPlaylists(chid, maxPages)  a channel's playlists ({id,title,n}); the new UI pages are small
//   await __channelSearch(chid, query)        playlists matching a query inside one channel (for channels with 100s)
//   __parsePlaylists2(await __search(q, 'EgIQAw%3D%3D'))   playlist search; 'EgIQAg%3D%3D' + __parseChannels = channel search
//   await __searchCont(d)                     next page of a search result
//   await __ytMeta2(videoId)                  title, channel, length, views, publish date, category, keywords, description,
//                                             playability (st/rs), embeddable; ~4/s is safe, faster gets bot-gated
//   await __grabThumb(videoId)                224x126 JPEG data URI of the mid-video frame (hosted copy thumbnails)
//   await __gzb64(text), __noise(n)           transfer helpers: gzip+base64 a payload; random padding
//
// Everything is read-only and uses the signed-out web client. See pipeline/NOTES.md for the pull protocol and
// pipeline/yt_pull_runner.js for pulling hundreds of playlists in the background.
(() => {
  const cfg = window.ytcfg && window.ytcfg.get ? window.ytcfg : null;
  const ctx = cfg ? cfg.get('INNERTUBE_CONTEXT') : null;
  window.__YT = Object.assign(window.__YT || {}, { key: cfg ? cfg.get('INNERTUBE_API_KEY') : '', cv: cfg ? cfg.get('INNERTUBE_CLIENT_VERSION') : '2.20240101.00.00', results: (window.__YT && window.__YT.results) || {} });
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const parseLen = s => { const m = String(s || '').trim().match(/^(\d+):(\d{2})(?::(\d{2}))?$/); if (!m) return null; return m[3] != null ? (+m[1]) * 3600 + (+m[2]) * 60 + (+m[3]) : (+m[1]) * 60 + (+m[2]); };
  window.text = function text(t){ if(!t) return ''; if(typeof t==='string') return t; if(t.simpleText) return t.simpleText; if(t.runs) return t.runs.map(r=>r.text).join(''); return ''; };
  const text = window.text;

  window.__gzb64 = async (text) => { const gz = new Uint8Array(await new Response(new Blob([text]).stream().pipeThrough(new CompressionStream('gzip'))).arrayBuffer()); let s=''; for(let i=0;i<gz.length;i+=0x8000){ s+=String.fromCharCode.apply(null, gz.subarray(i,i+0x8000)); } return btoa(s); };

  window.__noise = (n)=>{ let s=''; while(s.length<n){ const a=new Uint8Array(60000); crypto.getRandomValues(a); let t=''; for(let i=0;i<a.length;i+=0x8000){ t+=String.fromCharCode.apply(null,a.subarray(i,i+0x8000)); } s+=btoa(t);} return s.slice(0,n); };

  window.__browse = async function(body){ const context = ctx ? JSON.parse(JSON.stringify(ctx)) : {client:{clientName:'WEB', clientVersion:window.__YT.cv}}; context.client.hl='en'; context.client.gl='US'; const r = await fetch('/youtubei/v1/browse?key='+window.__YT.key+'&prettyPrint=false', {method:'POST', headers:{'Content-Type':'application/json','X-Youtube-Client-Name':'1','X-Youtube-Client-Version':context.client.clientVersion}, body: JSON.stringify(Object.assign({context}, body))}); return r.json(); };

  window.__walk = function(o, fn, depth=0){ if(!o || typeof o!=='object' || depth>60) return; fn(o); if(Array.isArray(o)){ for(const x of o) window.__walk(x, fn, depth+1); } else { for(const k in o) window.__walk(o[k], fn, depth+1); } };

  window.__playlistFull = async function(pid){
    const items=new Map(); let tokens=[]; const head={}; let order=0;
    const grab=(d)=>{ window.__walk(d, (o)=>{
      if(o.playlistVideoRenderer){ const v=o.playlistVideoRenderer; const by=v.shortBylineText||{}; const run=(by.runs||[])[0]||{}; const be=((run.navigationEndpoint||{}).browseEndpoint)||{}; let info=''; try{ info=text(v.videoInfo); }catch(e){}
        if(!items.has(v.videoId)) items.set(v.videoId, {id:v.videoId, title:text(v.title), len: v.lengthSeconds? +v.lengthSeconds : null, idx: ++order, ch: run.text||'', chid: be.browseId||'', info}); }
      if(o.lockupViewModel && /VIDEO/.test(o.lockupViewModel.contentType||'')){ const l=o.lockupViewModel; const id=l.contentId; if(items.has(id)) return; const md=(l.metadata||{}).lockupMetadataViewModel||{}; const rows=(((md.metadata||{}).contentMetadataViewModel||{}).metadataRows)||[]; let ch='',chid='',info='';
        try{ const p=rows[0].metadataParts[0]; ch=p.text.content; chid=p.text.commandRuns[0].onTap.innertubeCommand.browseEndpoint.browseId; }catch(e){}
        try{ info=rows[1].metadataParts.map(p=>p.text.content).join(' · '); }catch(e){}
        let len=null; try{ window.__walk(l.contentImage, x=>{ if(len==null && x.thumbnailBadgeViewModel){ const v=parseLen(x.thumbnailBadgeViewModel.text||''); if(v!=null) len=v; } }); }catch(e){}
        items.set(id, {id, title:text(md.title), len, idx: ++order, ch, chid, info}); }
      if(o.playlistHeaderRenderer){ const h=o.playlistHeaderRenderer; head.title=text(h.title); head.owner=text(h.ownerText); head.count=text(h.numVideosText); head.desc=text(h.descriptionText); try{ head.ownerId=h.ownerEndpoint.browseEndpoint.browseId; }catch(e){} }
      if(o.pageHeaderRenderer && !head.title){ head.title=o.pageHeaderRenderer.pageTitle||''; }
      if(o.playlistSidebarPrimaryInfoRenderer){ const h=o.playlistSidebarPrimaryInfoRenderer; head.title=head.title||text(h.title); head.desc=head.desc||text(h.description); try{ head.count=head.count||text(h.stats[0]); }catch(e){} }
      if(o.playlistSidebarSecondaryInfoRenderer){ try{ const vo=o.playlistSidebarSecondaryInfoRenderer.videoOwner.videoOwnerRenderer; head.owner=head.owner||text(vo.title); head.ownerId=head.ownerId||vo.navigationEndpoint.browseEndpoint.browseId; }catch(e){} }
      if(o.continuationCommand && o.continuationCommand.token) tokens.push(o.continuationCommand.token);
    }); };
    let d = await window.__browse({browseId:'VL'+pid}); grab(d);
    if(!head.desc){ try{ head.desc = d.metadata.playlistMetadataRenderer.description||''; head.title=head.title||d.metadata.playlistMetadataRenderer.title; }catch(e){} }
    let guard=0; while(tokens.length && guard<12){ const t=tokens[0]; tokens=[]; await sleep(300); const before=items.size; d=await window.__browse({continuation:t}); grab(d); guard++; if(items.size===before) break; }
    return Object.assign({pid}, head, {n: items.size, items:[...items.values()].sort((a,b)=>a.idx-b.idx)});
  };

  window.__search = async function(query, params){ const r = await fetch('/youtubei/v1/search?key='+window.__YT.key+'&prettyPrint=false', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({context:{client:{clientName:'WEB', clientVersion:window.__YT.cv, hl:'en', gl:'US'}}, query, params})}); return r.json(); };

  window.__searchCont = async function(d){ let tok=null; window.__walk(d, o=>{ if(!tok && o.continuationCommand && o.continuationCommand.token) tok=o.continuationCommand.token; }); if(!tok) return null; const base=ctx||{client:{clientName:'WEB',clientVersion:window.__YT.cv}}; const context=JSON.parse(JSON.stringify(base)); context.client.hl='en'; context.client.gl='US'; const r=await fetch('/youtubei/v1/search?key='+window.__YT.key+'&prettyPrint=false',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({context, continuation:tok})}); return r.json(); };

  window.__parsePlaylists2 = (d) => { const out=[]; window.__walk(d, (o)=>{
    if(o.lockupViewModel && /PLAYLIST/.test(o.lockupViewModel.contentType||'')){ const l=o.lockupViewModel; const md=(l.metadata||{}).lockupMetadataViewModel||{}; let ch='',chid='',verified=false,count=null;
      try{ const p=md.metadata.contentMetadataViewModel.metadataRows[0].metadataParts[0]; ch=p.text.content; chid=p.text.commandRuns[0].onTap.innertubeCommand.browseEndpoint.browseId; verified=!!(p.icon && /CHECK/.test(p.icon.name||'')); }catch(e){}
      try{ window.__walk(l.contentImage, x=>{ if(x.thumbnailBadgeViewModel && /video|lesson|episode/i.test(x.thumbnailBadgeViewModel.text||'')) count=parseInt((x.thumbnailBadgeViewModel.text||'').replace(/,/g,''))||count; }); }catch(e){}
      out.push({id:l.contentId, title:text(md.title), ch, chid, verified, count}); }
    if(o.playlistRenderer){ const p=o.playlistRenderer; let ch='',chid=''; try{ const run=p.shortBylineText.runs[0]; ch=run.text; chid=run.navigationEndpoint.browseEndpoint.browseId; }catch(e){} out.push({id:p.playlistId, title:text(p.title), ch, chid, verified:false, count:+(text(p.videoCount)||'').replace(/\D/g,'')||null}); }
  }); return out; };

  window.__parseChannels = (d) => { const out=[]; window.__walk(d, (o)=>{ if(o.channelRenderer){ const c=o.channelRenderer; let verified=false; try{ verified=(c.ownerBadges||[]).some(b=>/VERIFIED/.test(b.metadataBadgeRenderer.style)); }catch(e){} out.push({id:c.channelId, title:text(c.title), subs:text(c.videoCountText||c.subscriberCountText), desc:text(c.descriptionSnippet).slice(0,160), verified}); } }); return out; };

  window.__channelPlaylists = async function(chid, maxPages=20){ let d = await window.__browse({browseId: chid}); let params=null; window.__walk(d, o=>{ if(o.tabRenderer && o.tabRenderer.title==='Playlists'){ const ep=o.tabRenderer.endpoint||{}; params = ep.browseEndpoint && ep.browseEndpoint.params; } }); if(!params) return {error:'no playlists tab', chid};
    const out=new Map(); const grab=(d)=>{ const toks=[]; window.__walk(d, (o)=>{ if(o.gridPlaylistRenderer){ const p=o.gridPlaylistRenderer; out.set(p.playlistId, {title:text(p.title), n: parseInt(text(p.videoCountShortText))||null}); } if(o.lockupViewModel && /PLAYLIST/.test(o.lockupViewModel.contentType||'')){ const l=o.lockupViewModel; const md=l.metadata && l.metadata.lockupMetadataViewModel; let count=null; try{ window.__walk(l.contentImage, x=>{ if(x.thumbnailBadgeViewModel && /video|episode|lesson/i.test(x.thumbnailBadgeViewModel.text||'')) count=parseInt((x.thumbnailBadgeViewModel.text||'').replace(/,/g,''))||count; }); }catch(e){} out.set(l.contentId, {title: text(md && md.title), n:count}); } if(o.continuationCommand && o.continuationCommand.token) toks.push(o.continuationCommand.token); }); return toks; };
    await sleep(200); d = await window.__browse({browseId: chid, params}); let toks = grab(d); let pages=1; while(toks.length && pages<maxPages){ await sleep(250); const before=out.size; d = await window.__browse({continuation: toks[0]}); toks = grab(d); pages++; if(out.size===before) break; } return [...out.entries()].map(([id,v])=>({id, title:v.title, n:v.n})); };

  window.__channelSearch = async function(chid, query){
    const d = await window.__browse({browseId: chid, params: 'EgZzZWFyY2jyBgQKAloA', query});
    const out=new Map();
    window.__walk(d, (o)=>{
      if(o.playlistRenderer){ const p=o.playlistRenderer; out.set(p.playlistId, {id:p.playlistId, title:text(p.title), n:+(text(p.videoCount)||'').replace(/\D/g,'')||null}); }
      if(o.gridPlaylistRenderer){ const p=o.gridPlaylistRenderer; out.set(p.playlistId, {id:p.playlistId, title:text(p.title), n:parseInt(text(p.videoCountShortText))||null}); }
      if(o.lockupViewModel && /PLAYLIST/.test(o.lockupViewModel.contentType||'')){ const l=o.lockupViewModel; const md=l.metadata&&l.metadata.lockupMetadataViewModel; let count=null; try{ window.__walk(l.contentImage, x=>{ if(x.thumbnailBadgeViewModel && /video|lesson|episode/i.test(x.thumbnailBadgeViewModel.text||'')) count=parseInt((x.thumbnailBadgeViewModel.text||'').replace(/,/g,''))||count; }); }catch(e){} out.set(l.contentId, {id:l.contentId, title:text(md&&md.title), n:count}); }
    });
    return [...out.values()];
  };

  window.__makeMetaPayload = async function(ids){ const out={}; for(const id of ids){ const m=window.__YT.results[id]; if(m) out[id]=m; } const text=JSON.stringify(out); const b64=await window.__gzb64(text); const CH=230000; return {b64, total: Math.ceil(b64.length/CH), CH, n:Object.keys(out).length, textLen:text.length}; };

  window.__ytMeta2 = async function(id){ const context = ctx ? JSON.parse(JSON.stringify(ctx)) : {client:{clientName:'WEB', clientVersion: window.__YT.cv}}; context.client.hl='en'; context.client.gl='US'; const body = {context, videoId:id, contentCheckOk:true, racyCheckOk:true}; const r = await fetch('/youtubei/v1/player?key='+window.__YT.key+'&prettyPrint=false', {method:'POST', headers:{'Content-Type':'application/json','X-Youtube-Client-Name':'1','X-Youtube-Client-Version':context.client.clientVersion}, body: JSON.stringify(body)}); if(r.status!==200) return {id, http:r.status}; const d = await r.json(); const vd=d.videoDetails||{}; const mf=(d.microformat&&d.microformat.playerMicroformatRenderer)||{}; const ps=d.playabilityStatus||{}; return {id, st: ps.status, rs: ps.reason, title: vd.title, ch: vd.author, chid: vd.channelId, len: vd.lengthSeconds? +vd.lengthSeconds : null, views: vd.viewCount? +vd.viewCount : null, live: !!vd.isLiveContent, pub: mf.publishDate? mf.publishDate.slice(0,10) : null, cat: mf.category||null, kw: (vd.keywords||[]).slice(0,10), desc: (vd.shortDescription||'').slice(0,300), emb: ps.playableInEmbed===undefined? null : !!ps.playableInEmbed, unl: mf.isUnlisted===undefined? null : !!mf.isUnlisted}; };

  window.__grabThumb = (id) => new Promise((resolve) => {
    const tryUrl = (urls) => { if(!urls.length) return resolve(null); const im = new Image(); im.crossOrigin='anonymous'; im.onload = () => { if (im.naturalWidth < 200) return tryUrl(urls.slice(1)); try { const c=document.createElement('canvas'); c.width=224; c.height=126; const g=c.getContext('2d'); const r=Math.max(224/im.naturalWidth, 126/im.naturalHeight); const w=im.naturalWidth*r, h=im.naturalHeight*r; g.drawImage(im, (224-w)/2, (126-h)/2, w, h); resolve(c.toDataURL('image/jpeg', 0.58)); } catch(e) { resolve(null); } }; im.onerror = () => tryUrl(urls.slice(1)); im.src = urls[0]; };
    tryUrl([`https://i.ytimg.com/vi/${id}/mq2.jpg`, `https://i.ytimg.com/vi/${id}/hq2.jpg`, `https://i.ytimg.com/vi/${id}/mqdefault.jpg`]);
  });

  return 'yt helpers ready: key=' + (window.__YT.key ? 'ok' : 'MISSING') + ', context=' + (ctx ? 'page' : 'minimal');
})();

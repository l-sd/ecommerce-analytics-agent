(() => {
  const DATA = "./data/";
  const COLORS = ["#3687e2", "#1baab4", "#63b99a", "#e9a348", "#9176d5", "#e07370"];
  const PAGE_INFO = {
    overview: ["经营总览", "从订单表现、渠道贡献和经营趋势快速了解业务概况。"],
    channels: ["渠道与转化", "用配套流量表观察曝光、访客、加购与下单，并比较各渠道产出。"],
    products: ["商品分析", "拆解品类、品牌与 SKU 的 GMV 贡献，并用商品目录计算动销率。"],
    users: ["用户 / RFM", "查看复购、用户价值分层与消费贡献集中度。"],
    fulfilment: ["退款与履约", "用全量订单观察退款，用实际发货与签收记录衡量履约时效。"],
    quality: ["数据质量", "复核重复、缺失、金额异常和指标口径，查看订单级数据明细。"],
  };
  const $ = (q) => document.querySelector(q);
  const money = (n) => `¥${Number(n || 0).toLocaleString("zh-CN", { maximumFractionDigits: 0 })}`;
  const num = (n) => Number(n || 0).toLocaleString("zh-CN", { maximumFractionDigits: 2 });
  const pct = (n) => n == null ? "—" : `${(n * 100).toFixed(1)}%`;
  const safe = (s) => String(s ?? "—").replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const ratio = (a, b) => b ? a / b : null;
  const roundTiesToEven = (n) => { const base=Math.floor(n), fraction=n-base; return fraction===0.5 ? (base%2===0?base:base+1) : Math.round(n); };
  const sum = (xs, key) => xs.reduce((a, x) => a + (Number(x[key]) || 0), 0);
  let orders = [], traffic = [], products = [], page = "overview";
  let rawProfile = {};

  function csvRows(text) {
    const lines = []; let row = [], cell = "", quoted = false;
    text = text.replace(/^\uFEFF/, "");
    for (let i = 0; i < text.length; i++) {
      const ch = text[i];
      if (quoted) {
        if (ch === '"' && text[i + 1] === '"') { cell += '"'; i++; }
        else if (ch === '"') quoted = false;
        else cell += ch;
      } else if (ch === '"') quoted = true;
      else if (ch === ",") { row.push(cell); cell = ""; }
      else if (ch === "\n") { row.push(cell.replace(/\r$/, "")); lines.push(row); row = []; cell = ""; }
      else cell += ch;
    }
    if (cell.length || row.length) { row.push(cell.replace(/\r$/, "")); lines.push(row); }
    const headers = lines.shift() || [];
    return lines.filter((r) => r.length > 1 || r[0]).map((r) => Object.fromEntries(headers.map((h, i) => [h, r[i] ?? ""])));
  }
  async function loadCSV(file) {
    const res = await fetch(`${DATA}${file}`, { cache: "force-cache" });
    if (!res.ok) throw new Error(`数据文件加载失败（${file}，HTTP ${res.status}）`);
    return csvRows(await res.text());
  }
  function asNum(v) { if (v == null || String(v).trim() === "") return NaN; return Number(String(v).replace(/[¥,元\s]/g, "")); }
  function asDate(v) {
    const s = String(v ?? "").trim(); if (!s) return null;
    if (/^\d{8}$/.test(s)) return asDate(`${s.slice(0,4)}-${s.slice(4,6)}-${s.slice(6,8)}`);
    const m = s.match(/^(\d{4})[/-](\d{1,2})[/-](\d{1,2})(?:[ T](\d{1,2}):(\d{1,2})(?::(\d{1,2}))?)?/);
    if (!m) return null;
    const d = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3], +(m[4] || 0), +(m[5] || 0), +(m[6] || 0)));
    return Number.isNaN(d.getTime()) ? null : d;
  }
  const day = (d) => d ? d.toISOString().slice(0, 10) : "";
  const month = (d) => d ? day(d).slice(0, 7) : "未标注日期";
  function normaliseOrders(rows) {
    const seen = new Set();
    const cleaned = [];
    for (const raw of rows) {
      const id = raw["订单号"];
      if (seen.has(id)) continue;
      seen.add(id);
      const price = asNum(raw["单价"]), quantity = asNum(raw["数量"]), amount = price * quantity;
      cleaned.push({ ...raw, price, quantity, amount, date: asDate(raw["日期"]), shipDate: asDate(raw["发货时间"]), signDate: asDate(raw["签收时间"]), shipPromise: asNum(raw["承诺发货时效"]), deliveryPromise: asNum(raw["承诺送达时效"]), channel: raw["渠道"] || "未知", sku: raw["商品ID"] || "未知", product: raw["商品名称"] || "未知", category: raw["商品品类"] || "未知", user: raw["用户ID"] || "未知", status: raw["订单状态"] || "未知" });
    }
    return cleaned;
  }
  function rawQuality(rows) {
    const unique = new Set(); let missingDates=0, missingPrice=0, missingQty=0, zeroQty=0, negativeQty=0, missingAmount=0, mismatches=0, missingChannel=0, missingSku=0, missingUser=0;
    for (const r of rows) {
      unique.add(r["订单号"]);
      const price=asNum(r["单价"]), qty=asNum(r["数量"]), amount=asNum(r["金额"]);
      if (!asDate(r["日期"])) missingDates++;
      if (!Number.isFinite(price)) missingPrice++;
      if (!Number.isFinite(qty)) missingQty++;
      else { if (qty===0) zeroQty++; if(qty<0) negativeQty++; }
      if (!Number.isFinite(amount)) missingAmount++;
      if (Number.isFinite(price)&&Number.isFinite(qty)&&Number.isFinite(amount)&&Math.abs(amount-price*qty)>.01) mismatches++;
      if (!r["渠道"]) missingChannel++;
      if (!r["商品ID"]) missingSku++;
      if (!r["用户ID"]) missingUser++;
    }
    return { rows:rows.length, unique:unique.size, duplicates:rows.length-unique.size, missingDates, missingPrice, missingQty, zeroQty, negativeQty, missingAmount, mismatches, missingChannel, missingSku, missingUser };
  }
  function checkboxes() {
    const names = [...new Set(orders.map(o=>o.channel))].sort();
    $("#channel-options").innerHTML = names.map(n=>`<label><input type="checkbox" value="${safe(n)}" checked> ${safe(n)}</label>`).join("");
  }
  function filtered() {
    const start=$("#date-start").value, end=$("#date-end").value;
    const channels=new Set([...document.querySelectorAll("#channel-options input:checked")].map(x=>x.value));
    return orders.filter(o=>channels.has(o.channel)&&(!o.date||(o.date&&(!start||day(o.date)>=start)&&(!end||day(o.date)<=end))));
  }
  function group(rows, key, value="amount") {
    const m=new Map(); for(const r of rows){const k=key(r)??"未知";m.set(k,(m.get(k)||0)+(Number(r[value])||0));} return [...m].map(([name,val])=>({name,value:val})).sort((a,b)=>b.value-a.value);
  }
  function valid(rows) { return rows.filter(o=>!['已退款','已取消'].includes(o.status)&&Number.isFinite(o.amount)); }
  function aggregate(rows) {
    const good=valid(rows), gmv=sum(good,"amount"), allCount=rows.length;
    const channels=group(good,o=>o.channel);
    const monthly=group(good.filter(o=>o.date),o=>month(o.date));
    const categories=group(good,o=>o.category);
    const skuMap=new Map();
    for(const o of good){const key=o.product.replace(/\s+/g,"").toLowerCase();const x=skuMap.get(key)||{name:o.product,gmv:0,orders:0,quantity:0,ids:new Set()};x.gmv+=o.amount;x.quantity+=Number(o.quantity)||0;x.ids.add(o["订单号"]);x.orders=x.ids.size;skuMap.set(key,x);}
    const topProducts=[...skuMap.values()].sort((a,b)=>b.gmv-a.gmv).slice(0,15);
    const refund=rows.filter(o=>o.status==="已退款"), refundAmount=refund.reduce((a,o)=>a+Math.abs(o.amount||0),0);
    const byChannel=[...new Set(rows.map(o=>o.channel))].map(name=>{const cr=rows.filter(o=>o.channel===name);const rr=cr.filter(o=>o.status==="已退款");return {name,gmv:sum(good.filter(o=>o.channel===name),"amount"),orders:cr.length,refunds:rr.length,refundRate:ratio(rr.length,cr.length),refundAmount:rr.reduce((s,o)=>s+Math.abs(o.amount||0),0)};}).sort((a,b)=>b.refundRate-a.refundRate);
    const known=good.filter(o=>o.user!=="未知");
    const customers=new Map();
    for(const o of known){const x=customers.get(o.user)||{user:o.user,orders:new Set(),gmv:0,first:o.date,last:o.date};x.orders.add(o["订单号"]);x.gmv+=o.amount;if(o.date<x.first)x.first=o.date;if(o.date>x.last)x.last=o.date;customers.set(o.user,x);}
    const customerRows=[...customers.values()].map(x=>({...x,frequency:x.orders.size}));
    const rfmMap=new Map();
    for(const o of known.filter(x=>x.date)){const x=rfmMap.get(o.user)||{user:o.user,orders:new Set(),gmv:0,last:o.date};x.orders.add(o["订单号"]);x.gmv+=o.amount;if(o.date>x.last)x.last=o.date;rfmMap.set(o.user,x);}
    const datedCustomers=[...rfmMap.values()].map(x=>({...x,frequency:x.orders.size}));
    const cutoff=datedCustomers.length?Math.max(...datedCustomers.map(x=>x.last.getTime())):0;
    const rfmCustomers=datedCustomers.map(x=>({...x,recency:Math.round((cutoff-x.last.getTime())/86400000)}));
    const tier=(arr,field,descending=false)=>{if(arr.length<3)return new Map(arr.map(x=>[x.user,1]));const sorted=[...arr].sort((a,b)=>{const d=descending?b[field]-a[field]:a[field]-b[field];return d||a.user.localeCompare(b.user);});const n=sorted.length;const edge1=1+(n-1)/3,edge2=1+2*(n-1)/3;return new Map(sorted.map((x,i)=>{const rank=i+1;return [x.user,rank<=edge1?1:rank<=edge2?2:3]}));};
    const rt=tier(rfmCustomers,"recency",true),ft=tier(rfmCustomers,"frequency"),mt=tier(rfmCustomers,"gmv");
    const segs=new Map(["重要价值客户","重要挽留客户","潜力客户","一般客户"].map(n=>[n,{name:n,customers:0,gmv:0}]));
    for(const c of rfmCustomers){c.R=rt.get(c.user);c.F=ft.get(c.user);c.M=mt.get(c.user);c.segment=c.R===3&&c.F>=2&&c.M>=2?"重要价值客户":c.R===1&&(c.F>=2||c.M>=2)?"重要挽留客户":c.F==null||c.M==null?"一般客户":c.R>=2&&c.F===1?"潜力客户":"一般客户";const s=segs.get(c.segment);s.customers++;s.gmv+=c.gmv;}
    const shipped=rows.filter(o=>o.shipDate&&o.date);const shipLag=shipped.map(o=>({o,days:Math.floor((o.shipDate-o.date)/86400000)}));const late=shipLag.filter(x=>x.days>x.o.shipPromise);const delivered=rows.filter(o=>o.signDate&&o.shipDate);const deliveryLag=delivered.map(o=>({o,days:Math.floor((o.signDate-o.shipDate)/86400000)}));const overdue=deliveryLag.filter(x=>x.days>x.o.deliveryPromise);
    const funnelRows=traffic.filter(t=>{const dt=day(t.date);const s=$("#date-start").value,e=$("#date-end").value;const selected=new Set([...document.querySelectorAll("#channel-options input:checked")].map(x=>x.value));return selected.has(t.channel)&&(!dt||(!s||dt>=s)&&(!e||dt<=e));});
    const funnel=["曝光数","访客数","加购数","下单数"].map((key,i)=>({name:["曝光","访客","加购","下单"][i],value:funnelRows.reduce((a,x)=>a+(Number(x[key])||0),0)}));
    const trafficByChannel=[...new Set(funnelRows.map(t=>t.channel))].map(name=>{const ts=funnelRows.filter(t=>t.channel===name);const fo=funnelRows.filter(t=>t.channel===name);const trafficCount=key=>fo.reduce((a,t)=>a+(Number(t[key])||0),0);const orderGmv=byChannel.find(c=>c.name===name)?.gmv||0;return {name,exposure:trafficCount("曝光数"),visitors:trafficCount("访客数"),carts:trafficCount("加购数"),orders:trafficCount("下单数"),gmv:orderGmv,visitRate:ratio(trafficCount("访客数"),trafficCount("曝光数")),cartRate:ratio(trafficCount("加购数"),trafficCount("访客数")),conversion:ratio(trafficCount("下单数"),trafficCount("访客数"))};}).sort((a,b)=>b.exposure-a.exposure);
    const catalogOnSale=products.filter(p=>p["在售状态"]==="在售"), soldIds=new Set(good.map(o=>o.sku));
    const activeSold=catalogOnSale.filter(p=>soldIds.has(p["商品ID"])).length;
    const reasons=group(refund,o=>o["退款原因"],"one");
    for(const r of reasons) r.value=refund.filter(o=>(o["退款原因"]||"未知")===r.name).length;
    return {rows,good,gmv,allCount,channels,monthly,categories,topProducts,refund,refundAmount,byChannel,customers:customerRows,segments:[...segs.values()].sort((a,b)=>b.gmv-a.gmv),repeatCustomers:customerRows.filter(x=>x.frequency>=2).length,customerGmv:customerRows.reduce((a,x)=>a+x.gmv,0),customerOrderCount:customerRows.reduce((a,x)=>a+x.frequency,0),topCustomers:[...customerRows].sort((a,b)=>b.gmv-a.gmv).slice(0,Math.max(1,roundTiesToEven(customerRows.length*.1))),shipped,shipLag,late,delivered,deliveryLag,overdue,funnel,trafficByChannel,catalogOnSale,activeSold,reasons};
  }
  function barPanel(title, rows, format=(x)=>num(x), options={}) {
    if(!rows.length) return panel(title,'<div class="empty">当前筛选下暂无可用数据</div>',options);
    const max=Math.max(...rows.map(x=>x.value),1), limit=options.limit||rows.length;
    const body=rows.slice(0,limit).map((x,i)=>`<div class="bar-row"><span class="bar-label" title="${safe(x.name)}">${safe(x.name)}</span><span class="bar-track"><span class="bar-fill" style="display:block;width:${Math.max(1,x.value/max*100)}%;background:${COLORS[i%COLORS.length]}"></span></span><span class="bar-value">${safe(format(x.value,x))}</span></div>`).join("");
    return panel(title,`<div class="chart-bars">${body}</div>`,options);
  }
  function panel(title,body,options={}) {return `<article class="panel ${options.wide?'wide':''}"><div class="panel-heading"><div><h2>${title}</h2>${options.note?`<p>${options.note}</p>`:""}</div>${options.tag?`<span class="panel-tag">${options.tag}</span>`:""}</div>${body}${options.definition?`<p class="definition">${options.definition}</p>`:""}</article>`;}
  function table(headers, rows) {return `<div class="table-wrap"><table><thead><tr>${headers.map(h=>`<th>${safe(h)}</th>`).join("")}</tr></thead><tbody>${rows.length?rows.map(r=>`<tr>${r.map(c=>`<td>${c}</td>`).join("")}</tr>`).join(""):`<tr><td colspan="${headers.length}">暂无数据</td></tr>`}</tbody></table></div>`;}
  function trendPanel(rows) {
    if(!rows.length)return panel("月度 GMV 趋势",'<div class="empty">当前筛选下暂无可用数据</div>');
    const w=650,h=175,pad={l:8,r:12,t:16,b:25};const values=rows.map(x=>x.value);const max=Math.max(...values,1);const points=rows.map((x,i)=>{const px=pad.l+(rows.length===1?0:i*(w-pad.l-pad.r)/(rows.length-1));const py=pad.t+(h-pad.t-pad.b)*(1-x.value/max);return [px,py,x];});const path=points.map((p,i)=>`${i?'L':'M'}${p[0]},${p[1]}`).join(' ');const poly=`${pad.l},${h-pad.b} ${points.map(p=>`${p[0]},${p[1]}`).join(' ')} ${w-pad.r},${h-pad.b}`;
    const labels=rows.map((x,i)=>i%Math.ceil(rows.length/6)===0||i===rows.length-1?`<text x="${points[i][0]}" y="${h-5}" text-anchor="middle" class="trend-label">${safe(x.name.slice(5))}</text>`:"").join("");const dots=points.map(p=>`<circle cx="${p[0]}" cy="${p[1]}" r="3.5" class="trend-point"><title>${safe(p[2].name)} · ${money(p[2].value)}</title></circle>`).join("");
    return panel("月度有效 GMV 趋势",`<svg class="trend" viewBox="0 0 ${w} ${h}" role="img" aria-label="月度 GMV 折线图"><defs><linearGradient id="trendFill" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#3889e5" stop-opacity=".18"/><stop offset="1" stop-color="#3889e5" stop-opacity="0"/></linearGradient></defs><line x1="${pad.l}" y1="${h-pad.b}" x2="${w-pad.r}" y2="${h-pad.b}" class="trend-grid"/><line x1="${pad.l}" y1="${pad.t+40}" x2="${w-pad.r}" y2="${pad.t+40}" class="trend-grid"/><line x1="${pad.l}" y1="${pad.t+85}" x2="${w-pad.r}" y2="${pad.t+85}" class="trend-grid"/><polygon points="${poly}" class="trend-area"/><path d="${path}" class="trend-line"/>${dots}${labels}</svg><div class="legend"><span><i></i>有效 GMV</span><span>按下单日期汇总</span></div>`,{note:"筛选范围内按月聚合，未标注日期的订单不进入趋势图。"});
  }
  function kpis(a) {
    const values=[["有效 GMV",money(a.gmv),"排除退款与取消订单","¥"],["有效订单",num(a.good.length),"按订单号去重","▤"],["客单价",money(ratio(a.gmv,a.good.length)),"有效 GMV ÷ 有效订单","↗"],["有效商品件数",num(sum(a.good,"quantity")),"有效订单商品数量","▧"],["退款率",pct(ratio(a.refund.length,a.rows.length)),"退款订单 ÷ 全量订单","↻"]];
    $("#kpis").innerHTML=values.map(([label,value,note,glyph])=>`<article class="kpi-card"><div class="kpi-top"><span>${label}</span><span class="kpi-glyph">${glyph}</span></div><div class="kpi-value">${value}</div><div class="kpi-note">${note}</div></article>`).join("");
  }
  function overview(a) {
    const cumulative=[];let acc=0;const top=a.topProducts.map(x=>{acc+=x.gmv;return {name:x.name,value:x.gmv,share:acc/a.gmv};});
    const rows=a.channels.map(x=>({name:x.name,value:x.value}));
    return trendPanel(a.monthly)+barPanel("渠道 GMV 贡献",rows,money,{note:"有效 GMV 按销售渠道汇总。"})+barPanel("商品 GMV 集中度 · TOP 15",top,(v,x)=>`${money(v)} · 累计 ${pct(x.share)}`,{wide:true,note:"按商品名称归一化合并，展示各 SKU 贡献及累计占比。"});
  }
  function channelsPage(a) {
    const funnelRows=a.funnel.map((x,i)=>({name:x.name,value:x.value}));
    const channelRows=a.trafficByChannel.map(x=>[safe(x.name),num(x.exposure),num(x.visitors),num(x.carts),num(x.orders),pct(x.conversion),money(x.gmv)]);
    return barPanel("流量转化漏斗",funnelRows,num,{note:"曝光、访客、加购来自配套流量表；下单数由订单明细回填。",definition:"访客率 = 访客 ÷ 曝光；加购率 = 加购 ÷ 访客；下单转化率 = 下单 ÷ 访客。"})+panel("渠道流量与成交对照",table(["渠道","曝光","访客","加购","下单","下单转化率","有效 GMV"],channelRows),{note:"成交金额使用有效订单；流量指标来自配套流量表。"})+panel("指标口径",'<div class="quality-list"><div class="quality-item"><span>流量数据来源</span><strong>配套日 × 渠道流量表</strong></div><div class="quality-item"><span>筛选口径</span><strong>日期范围与所选渠道</strong></div><div class="quality-item"><span>守恒关系</span><strong>下单数与订单明细对齐</strong></div><div class="quality-item"><span>限制</span><strong>模拟数据不代表真实转化水平</strong></div></div>',{wide:true});
  }
  function productsPage(a) {
    const category=a.categories.map(x=>({name:x.name,value:x.value}));
    const skus=a.topProducts.map(x=>({name:x.name,value:x.gmv}));
    const topBrand=group(a.good,o=>{const p=products.find(x=>x["商品ID"]===o.sku);return p?.["品牌"]||"未知";}).slice(0,10);
    const sellPct=ratio(a.activeSold,a.catalogOnSale.length);
    return barPanel("品类 GMV 结构",category,money,{note:"按商品品类聚合有效订单金额。"})+barPanel("品牌 GMV TOP 10",topBrand,money,{note:"品牌通过商品主数据表匹配。"})+barPanel("商品 GMV 排行 · TOP 15",skus,money,{wide:true,note:"商品名称按 GMV 排序完整展示。"})+panel("商品动销",`<div class="stat-strip"><div class="stat-box"><span>在售 SKU（目录）</span><strong>${num(a.catalogOnSale.length)}</strong></div><div class="stat-box"><span>有销量 SKU</span><strong>${num(a.activeSold)}</strong></div><div class="stat-box"><span>动销率</span><strong>${pct(sellPct)}</strong></div><div class="stat-box"><span>未动销 SKU</span><strong>${num(Math.max(0,a.catalogOnSale.length-a.activeSold))}</strong></div></div><p class="definition">动销率 = 有销量的在售 SKU ÷ 商品目录中的在售 SKU。商品目录是唯一分母来源。</p>`,{wide:true});
  }
  function usersPage(a) {
    const gmv= a.customerGmv, rfmGmv=a.segments.reduce((s,x)=>s+x.gmv,0);
    const segRows=a.segments.map(x=>[safe(x.name),num(x.customers),money(x.gmv),pct(ratio(x.gmv,rfmGmv))]);
    const repeat=a.repeatCustomers, cust=a.customers.length;
    const topShare=ratio(a.topCustomers.reduce((s,x)=>s+x.gmv,0),a.gmv);
    return panel("用户复购与价值概况",`<div class="stat-strip"><div class="stat-box"><span>有效客户</span><strong>${num(cust)}</strong></div><div class="stat-box"><span>复购客户</span><strong>${num(repeat)}</strong></div><div class="stat-box"><span>复购率</span><strong>${pct(ratio(repeat,cust))}</strong></div><div class="stat-box"><span>客均有效订单</span><strong>${num(ratio(a.customerOrderCount,cust))}</strong></div></div><p class="definition">复购客户为观察窗口内有效订单数 ≥ 2 的已知用户。未合并同一自然人的多账号。</p>`,{wide:true})+panel("RFM 用户分层",table(["分层","客户数","贡献 GMV","客户 GMV 占比"],a.segments.map(x=>[safe(x.name),num(x.customers),money(x.gmv),pct(ratio(x.gmv,rfmGmv))])),{note:"R=最近一次购买距窗口结束的天数；F=有效订单频次；M=有效消费金额，均按三分位分层。"})+barPanel("用户 GMV 集中度",[{name:`GMV 前 10% 用户（${a.topCustomers.length} 人）`,value:(topShare||0)*100}],v=>pct(v/100),{note:"用于观察用户贡献集中程度，不代表未来价值。"})+panel("分析边界",'<div class="quality-list"><div class="quality-item"><span>客户标识</span><strong>模拟用户 ID</strong></div><div class="quality-item"><span>历史窗口</span><strong>仅含当前数据区间</strong></div><div class="quality-item"><span>新客定义</span><strong>无法区分窗口前老客</strong></div><div class="quality-item"><span>数据性质</span><strong>合成练习数据</strong></div></div>',{wide:true});
  }
  function fulfilmentPage(a) {
    const reasons=a.reasons.map(x=>({name:x.name,value:x.value}));
    const lateRate=ratio(a.late.length,a.shipLag.length), overdueRate=ratio(a.overdue.length,a.deliveryLag.length), avgShip=ratio(a.shipLag.reduce((s,x)=>s+x.days,0),a.shipLag.length), avgDelivery=ratio(a.deliveryLag.reduce((s,x)=>s+x.days,0),a.deliveryLag.length);
    const byChannel=a.byChannel.map(x=>[safe(x.name),num(x.orders),num(x.refunds),pct(x.refundRate),money(x.refundAmount||0)]);
    const dataAvailable=a.shipped.length>0;
    return panel("退款指标 · 全量订单口径",`<div class="stat-strip"><div class="stat-box"><span>全量订单</span><strong>${num(a.rows.length)}</strong></div><div class="stat-box"><span>退款订单</span><strong>${num(a.refund.length)}</strong></div><div class="stat-box"><span>退款率</span><strong>${pct(ratio(a.refund.length,a.rows.length))}</strong></div><div class="stat-box"><span>退款金额（绝对值）</span><strong>${money(a.refundAmount)}</strong></div></div>${table(["渠道","全量订单","退款订单","退款率","退款金额"],byChannel)}<p class="definition">退款率 = 退款订单 ÷ 全量订单；核心 GMV 指标排除退款订单，两种分母不可混用。</p>`,{wide:true})+barPanel("退款原因",reasons,num,{note:"退款原因来自模拟字段。"})+panel("履约时效与异常",dataAvailable?`<div class="stat-strip"><div class="stat-box"><span>已发货订单</span><strong>${num(a.shipLag.length)}</strong></div><div class="stat-box"><span>平均发货时效</span><strong>${num(avgShip)} 天</strong></div><div class="stat-box"><span>迟发率</span><strong>${pct(lateRate)}</strong></div><div class="stat-box"><span>签收订单 · 逾期率</span><strong>${num(a.deliveryLag.length)} · ${pct(overdueRate)}</strong></div></div><p class="definition">迟发率 = 超过承诺发货时效订单 ÷ 已产生发货时间订单；逾期率 = 超过承诺送达时效订单 ÷ 已签收订单。</p>`:'<div class="empty">当前筛选下暂无发货/签收记录</div>',{note:"发货时效与签收时效使用订单记录中的实际时间与承诺时效。"});
  }
  function qualityPage(a) {
    const q=rawProfile;
    const pairs=[["原始订单行",q.rows],["去重后订单",q.unique],["重复记录（按订单号）",q.duplicates],["日期缺失或无法解析",q.missingDates],["单价缺失 / 无法解析",q.missingPrice],["数量缺失",q.missingQty],["数量为 0",q.zeroQty],["负数量（退款记录）",q.negativeQty],["金额缺失",q.missingAmount],["金额与单价 × 数量不一致",q.mismatches],["渠道缺失",q.missingChannel],["商品 ID 缺失",q.missingSku],["用户 ID 缺失",q.missingUser]];
    const cells=pairs.map(([label,value])=>`<div class="quality-item"><span>${label}</span><strong>${num(value)}</strong></div>`).join("");
    return panel("原始数据体检",`<div class="quality-list">${cells}</div>`,{wide:true,note:"质量计数基于全部 4,999 行原始样本；清洗按订单号保留首条，并按单价 × 数量重算金额。"})+panel("关键指标定义",table(["指标","计算口径","使用范围"],[["有效 GMV","有效订单金额之和","状态非已退款/已取消"],["客单价","有效 GMV ÷ 有效订单数","与 GMV 同一分母"],["退款率","退款订单 ÷ 全量订单","退款与履约页面"],["下单转化率","流量表下单数 ÷ 访客数","只使用配套流量表"],["动销率","有销量在售 SKU ÷ 在售 SKU","分母来自商品目录"],["迟发率","超时发货订单 ÷ 已发货订单","不含待发货订单"]]),{wide:true,note:"缺少对应字段时不推算或填补业务指标。"})+panel("分析校验",'<div class="quality-list"><div class="quality-item"><span>订单粒度</span><strong>按订单号去重</strong></div><div class="quality-item"><span>数据可追溯</span><strong>原始行 + 清洗后明细</strong></div><div class="quality-item"><span>流量转化来源</span><strong>配套流量表</strong></div><div class="quality-item"><span>动销率分母来源</span><strong>商品目录</strong></div></div>',{wide:true});
  }
  function renderDetails(rows) {
    const cols=["订单号","日期","渠道","商品名称","商品品类","数量","金额","用户ID","订单状态"];
    const display=[...rows].sort((a,b)=>(b.date?.getTime()||0)-(a.date?.getTime()||0));
    $("#detail-count").textContent=`${num(rows.length)} 行 · 当前展示 ${Math.min(500,display.length)} 行`;
    $("#detail-table").innerHTML=`<thead><tr>${cols.map(c=>`<th>${safe(c)}</th>`).join("")}</tr></thead><tbody>${display.slice(0,500).map(o=>`<tr>${[o["订单号"],o["日期"],o.channel,o.product,o.category,num(o.quantity),money(o.amount),o.user,o.status].map(x=>`<td>${safe(x)}</td>`).join("")}</tr>`).join("")}</tbody>`;
  }
  function render() {
    const rows=filtered();const a=aggregate(rows);const [title,desc]=PAGE_INFO[page];
    $("#page-name").textContent=title;$("#page-title").textContent=title;$("#page-desc").textContent=desc;
    document.querySelectorAll(".nav-item").forEach(b=>b.classList.toggle("active",b.dataset.page===page));
    kpis(a);
    const renderers={overview,channels:channelsPage,products:productsPage,users:usersPage,fulfilment:fulfilmentPage,quality:qualityPage};
    $("#page-content").innerHTML=renderers[page](a);
    renderDetails(rows);
    window.currentDashboard={a,rows};
  }
  function download(name,text,type="text/plain;charset=utf-8") {const blob=new Blob(["\uFEFF",text],{type});const url=URL.createObjectURL(blob);const a=document.createElement("a");a.href=url;a.download=name;a.click();URL.revokeObjectURL(url);}
  function downloadOrders() {const {rows}=window.currentDashboard;const headers=["订单号","日期","渠道","商品ID","商品名称","单价","数量","金额","用户ID","收货省份","订单状态","商品品类","承诺发货时效","物流商","承诺送达时效","发货时间","签收时间","退款原因"];const quote=x=>`"${String(x??"").replace(/"/g,'""')}"`;const lines=[headers.map(quote).join(","),...rows.map(o=>headers.map(h=>quote(o[h])).join(","))];download("ecommerce-filtered-orders.csv",lines.join("\r\n"),"text/csv;charset=utf-8");}
  function downloadSummary() {const {a}=window.currentDashboard;const out={notice:"模拟练习数据，不代表真实企业经营",filters:{start:$("#date-start").value||null,end:$("#date-end").value||null,channels:[...document.querySelectorAll("#channel-options input:checked")].map(x=>x.value)},kpi:{raw_rows:rawProfile.rows,filtered_unique_orders:a.rows.length,valid_orders:a.good.length,valid_gmv:Number(a.gmv.toFixed(2)),aov:Number((ratio(a.gmv,a.good.length)||0).toFixed(2)),refund_orders:a.refund.length,refund_rate:ratio(a.refund.length,a.rows.length)},channel:a.byChannel,traffic_funnel:a.funnel,product_top15:a.topProducts.map(x=>({product:x.name,gmv:Number(x.gmv.toFixed(2))})),rfm:a.segments,fulfilment:{shipped_orders:a.shipped.length,late_orders:a.late.length,late_rate:ratio(a.late.length,a.shipped.length),delivered_orders:a.delivered.length,overdue_orders:a.overdue.length,overdue_rate:ratio(a.overdue.length,a.delivered.length)},limitations:["所有订单、流量与商品数据为固定种子生成的模拟数据。","退款率以全量订单为分母，核心 KPI 使用有效订单口径。","转化率使用配套流量表，动销率分母使用商品目录。"]};download("ecommerce-analysis-summary.json",JSON.stringify(out,null,2),"application/json;charset=utf-8");}
  async function start() {
    try {
      const [raw,trafficRows,catalogRows]=await Promise.all([loadCSV("portfolio_demo/synthetic_orders.csv"),loadCSV("portfolio_demo/synthetic_traffic.csv"),loadCSV("portfolio_demo/synthetic_products.csv")]);
      rawProfile=rawQuality(raw);orders=normaliseOrders(raw);traffic=trafficRows.map(t=>({...t,date:asDate(t["日期"]),channel:t["渠道"]||"未知"}));products=catalogRows;
      const dates=orders.map(o=>o.date).filter(Boolean).map(day).sort();$("#date-start").min=dates[0];$("#date-start").max=dates.at(-1);$("#date-end").min=dates[0];$("#date-end").max=dates.at(-1);$("#date-start").value=dates[0];$("#date-end").value=dates.at(-1);
      checkboxes();document.querySelectorAll(".nav-item").forEach(b=>b.addEventListener("click",()=>{page=b.dataset.page;render();window.scrollTo({top:0,behavior:"smooth"});}));
      document.querySelectorAll("#channel-options input").forEach(x=>x.addEventListener("change",render));$("#date-start").addEventListener("change",render);$("#date-end").addEventListener("change",render);
      $("#reset-filter").addEventListener("click",()=>{document.querySelectorAll("#channel-options input").forEach(x=>x.checked=true);$("#date-start").value=dates[0];$("#date-end").value=dates.at(-1);render();});
      $("#download-orders").addEventListener("click",downloadOrders);$("#download-summary").addEventListener("click",downloadSummary);render();
    } catch(error) {$("#error").hidden=false;$("#error").textContent=`Demo 加载失败：${error.message}。请从 GitHub Pages 站点打开，不要直接双击 index.html。`;$("#kpis").innerHTML="";}
  }
  start();
})();

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
    report: ["分析报告", "汇总当前筛选范围内的经营表现、主要发现与数据限制。"],
  };
  const $ = (q) => document.querySelector(q);
  const HEADER_ALIASES = {
    "订单号":"订单号","订单编号":"订单号","订单id":"订单号","订单 ID":"订单号","平台订单号":"订单号","orderid":"订单号","order_id":"订单号","order no":"订单号","order number":"订单号","子订单号":"订单号","交易订单号":"订单号",
    "日期":"日期","下单时间":"日期","下单日期":"日期","下单日期时间":"日期","拍下时间":"日期","订单时间":"日期","订单日期":"日期","创建时间":"日期","订单创建时间":"日期","付款时间":"日期","支付时间":"日期","支付日期":"日期","order date":"日期","order_time":"日期","created at":"日期","created_at":"日期",
    "渠道":"渠道","销售渠道":"渠道","平台":"渠道","店铺平台":"渠道","店铺名称":"渠道","来源渠道":"渠道","channel":"渠道","platform":"渠道",
    "商品id":"商品ID","sku":"商品ID","skuid":"商品ID","sku_id":"商品ID","商品编号":"商品ID","货号":"商品ID",
    "商品名称":"商品名称","产品名称":"商品名称","宝贝标题":"商品名称","宝贝名称":"商品名称","商品标题":"商品名称","product":"商品名称","product name":"商品名称","product_name":"商品名称",
    "单价":"单价","商品单价":"单价","商品价格":"单价","成交单价":"单价","销售单价":"单价","price":"单价","unitprice":"单价","unit_price":"单价",
    "数量":"数量","商品数量":"数量","购买数量":"数量","成交数量":"数量","件数":"数量","qty":"数量","quantity":"数量",
    "金额":"金额","金额元":"金额","实付金额":"金额","实付金额元":"金额","订单实付金额":"金额","商品实付金额":"金额","实付款":"金额","实付款金额":"金额","买家实付款":"金额","支付金额":"金额","支付金额元":"金额","成交金额":"金额","成交总额":"金额","订单金额":"金额","订单金额元":"金额","商品金额":"金额","商品总价":"金额","销售额":"金额","销售金额":"金额","付款金额":"金额","实收金额":"金额","总金额":"金额","实际支付金额":"金额","买家实际支付金额":"金额","amount":"金额","total":"金额","totalamount":"金额","total_amount":"金额","paymentamount":"金额","payment_amount":"金额",
    "用户id":"用户ID","客户id":"用户ID","买家id":"用户ID","买家昵称":"用户ID","买家账号":"用户ID","用户编号":"用户ID","客户编号":"用户ID","会员id":"用户ID","userid":"用户ID","user_id":"用户ID","customer id":"用户ID","customer_id":"用户ID",
    "收货省份":"收货省份","省份":"收货省份","收货地址":"收货省份","收货地区":"收货省份","province":"收货省份",
    "订单状态":"订单状态","状态":"订单状态","交易状态":"订单状态","订单交易状态":"订单状态","售后状态":"订单状态","status":"订单状态","order status":"订单状态","order_status":"订单状态",
    "商品品类":"商品品类","品类":"商品品类","商品分类":"商品品类","商品类目":"商品品类","分类":"商品品类","类目":"商品品类","category":"商品品类",
    "发货时间":"发货时间","发货日期":"发货时间","出库时间":"发货时间","shipping time":"发货时间","ship_date":"发货时间",
    "签收时间":"签收时间","收货时间":"签收时间","送达时间":"签收时间","妥投时间":"签收时间","delivery time":"签收时间","sign_date":"签收时间",
    "承诺发货时效":"承诺发货时效","发货时效":"承诺发货时效","承诺发货天数":"承诺发货时效","承诺送达时效":"承诺送达时效","送达时效":"承诺送达时效","承诺送达天数":"承诺送达时效",
    "物流商":"物流商","快递公司":"物流商","承运商":"物流商","快递名称":"物流商","物流公司":"物流商","carrier":"物流商",
    "退款原因":"退款原因","退货退款原因":"退款原因","售后原因":"退款原因","refund reason":"退款原因","refund_reason":"退款原因",
  };
  const HEADER_KEY = (s) => String(s ?? "").trim().toLowerCase().replace(/[\s_\-（）():：]/g, "");
  const ALIAS_LOOKUP = new Map(Object.entries(HEADER_ALIASES).map(([alias, canonical]) => [HEADER_KEY(alias), canonical]));
  const money = (n) => `¥${Number(n || 0).toLocaleString("zh-CN", { maximumFractionDigits: 0 })}`;
  const num = (n) => Number(n || 0).toLocaleString("zh-CN", { maximumFractionDigits: 2 });
  const pct = (n) => n == null ? "—" : `${(n * 100).toFixed(1)}%`;
  const safe = (s) => String(s ?? "—").replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const ratio = (a, b) => b ? a / b : null;
  const roundTiesToEven = (n) => { const base=Math.floor(n), fraction=n-base; return fraction===0.5 ? (base%2===0?base:base+1) : Math.round(n); };
  const sum = (xs, key) => xs.reduce((a, x) => a + (Number(x[key]) || 0), 0);
  let orders = [], traffic = [], products = [], page = "overview", datasetMeta = { demo:true, filename:"" }, sampleData = null, dateBounds = ["",""];
  let rawProfile = {};

  function csvRows(text, delimiter) {
    if (!delimiter) {
      const firstLine = text.replace(/^\uFEFF/, "").split(/\r?\n/, 1)[0] || "";
      delimiter = [",", "\t", ";"].map(d=>[d,[...firstLine].filter(ch=>ch===d).length]).sort((a,b)=>b[1]-a[1])[0][0];
    }
    const lines = []; let row = [], cell = "", quoted = false;
    text = text.replace(/^\uFEFF/, "");
    for (let i = 0; i < text.length; i++) {
      const ch = text[i];
      if (quoted) {
        if (ch === '"' && text[i + 1] === '"') { cell += '"'; i++; }
        else if (ch === '"') quoted = false;
        else cell += ch;
      } else if (ch === '"') quoted = true;
      else if (ch === delimiter) { row.push(cell); cell = ""; }
      else if (ch === "\n") { row.push(cell.replace(/\r$/, "")); lines.push(row); row = []; cell = ""; }
      else cell += ch;
    }
    if (cell.length || row.length) { row.push(cell.replace(/\r$/, "")); lines.push(row); }
    const headers = (lines.shift() || []).map(h=>h.trim());
    return lines.filter((r) => r.length > 1 || r[0]).map((r) => Object.fromEntries(headers.map((h, i) => [h, (r[i] ?? "").trim()])));
  }
  async function loadCSV(file) {
    const res = await fetch(`${DATA}${file}`, { cache: "force-cache" });
    if (!res.ok) throw new Error(`数据文件加载失败（${file}，HTTP ${res.status}）`);
    return csvRows(await res.text());
  }
  async function parseUpload(file) {
    if (/\.xlsx?$/i.test(file.name)) throw new Error("在线版暂不读取 Excel 工作簿；请在 Excel 中另存为 CSV UTF-8 后再上传。");
    if (file.size > 20 * 1024 * 1024) throw new Error("文件超过 20 MB。请先按日期筛选或拆分 CSV 后再上传。");
    let text;
    const bytes=await file.arrayBuffer();
    try { text=new TextDecoder("utf-8",{fatal:true}).decode(bytes); }
    catch { text=new TextDecoder("gb18030").decode(bytes); }
    const sourceRows=csvRows(text);
    if(!sourceRows.length) throw new Error("文件没有数据行，请检查表头和内容。");
    const inputHeaders=Object.keys(sourceRows[0]);
    const mapped=inputHeaders.map(header=>({header,canonical:ALIAS_LOOKUP.get(HEADER_KEY(header))}));
    const fields=new Set(mapped.map(x=>x.canonical).filter(Boolean));
    const amountPossible=fields.has("金额")||(fields.has("单价")&&fields.has("数量"));
    if(!fields.has("订单号")) throw new Error("无法识别订单号列。订单号是计算去重订单数和客单价的必需字段；可下载模板查看列名。");
    if(!amountPossible) throw new Error("无法识别金额列。至少需要金额/实付金额，或同时提供单价和数量；可下载模板查看列名。");
    for(const field of fields){const matches=mapped.filter(x=>x.canonical===field);if(matches.length>1) throw new Error(`多列都匹配到“${field}”（${matches.map(x=>x.header).join("、")}），请保留一列后重试。`);}
    const rows=sourceRows.map((source,index)=>{
      const row={};for(const {header,canonical} of mapped)if(canonical)row[canonical]=source[header]??"";
      let amount=asNum(row["金额"]),price=asNum(row["单价"]),quantity=asNum(row["数量"]);
      if(!Number.isFinite(amount)&&Number.isFinite(price)&&Number.isFinite(quantity)) amount=price*quantity;
      row["订单号"]=row["订单号"]||`导入行-${index+1}`;
      row["日期"]=row["日期"]||"";
      row["单价"]=Number.isFinite(price)?price:"";
      row["数量"]=Number.isFinite(quantity)?quantity:"";
      row["金额"]=Number.isFinite(amount)?amount:"";
      const status=String(row["订单状态"]??"").trim().toLowerCase();
      if(/退款|退货退款|已退|refund/.test(status)) row["订单状态"]="已退款";
      else if(/未付款|未支付|待付款|待支付|等待付款|unpaid|pending payment/.test(status)) row["订单状态"]="待付款";
      else if(/取消|作废|关闭|cancel|void/.test(status)) row["订单状态"]="已取消";
      else if(!row["订单状态"]||/完成|成功|已付款|已支付|已发货|已签收|complete|success|paid|shipped|delivered/.test(status)) row["订单状态"]="已完成";
      return row;
    });
    if(!rows.some(r=>Number.isFinite(asNum(r["金额"])))) throw new Error("金额列中没有可识别的数字，请检查币种符号和单元格内容。");
    return {rows,fields:[...fields],inputHeaders};
  }
  function setDateRange() {
    const dates=orders.map(o=>o.date).filter(Boolean).map(day).sort();
    dateBounds=[dates[0]||"",dates.at(-1)||""];
    for(const selector of ["#date-start","#date-end"]){$(selector).min=dateBounds[0];$(selector).max=dateBounds[1];}
    $("#date-start").value=dateBounds[0];$("#date-end").value=dateBounds[1];
  }
  function setDataset(rawRows, meta, nextTraffic=[], nextProducts=[]) {
    datasetMeta=meta;rawProfile=rawQuality(rawRows);orders=normaliseOrders(rawRows);
    traffic=nextTraffic.map(t=>({...t,date:asDate(t["日期"]),channel:t["渠道"]||"未知"}));products=nextProducts;
    setDateRange();checkboxes();
    const notice=$("#data-notice");
    notice.querySelector("strong").textContent=meta.demo?"模拟练习数据":"已载入用户文件";
    notice.querySelector("span").textContent=meta.demo?`固定种子生成 · ${num(rawRows.length)} 行原始记录 · 含 ${num(rawProfile.duplicates)} 行重复记录 · 不代表真实企业经营情况`:`${meta.filename} · ${num(rawRows.length)} 行 · 数据只在此浏览器本地计算，未上传服务器`;
    $("#upload-card").classList.toggle("has-file",!meta.demo);
    $("#upload-title").textContent=meta.demo?"上传订单数据，生成专属分析":"订单文件已载入";
    $("#upload-help").textContent=meta.demo?"支持 CSV / TSV，点击选择文件或拖拽到此区域。至少包含订单号和金额（或单价、数量）；Excel 请先另存为 CSV。": "可继续拖入新文件替换当前数据。分析仅在此浏览器本地计算，不会上传服务器。";
    $("#upload-status").textContent=meta.demo?"当前展示可交互的模拟数据":`✓ ${meta.filename} · ${num(rawRows.length)} 行已载入`;
    $("#upload-button-label").textContent=meta.demo?"点击上传文件":"重新上传文件";
    $(".demo-badge").innerHTML=`<span></span>${meta.demo?"模拟数据 · 仅用于演示":"自有数据 · 本地处理"}`;
    $("#footer-note").textContent=meta.demo?"指标仅按当前模拟数据计算。GMV 与订单金额使用有效订单口径；退款率以全量订单为分母；转化率只使用配套流量表。":"金额按明细行汇总，订单数按订单号去重。有效 GMV 排除退款、取消和待付款订单；是否能识别这些状态取决于文件是否提供订单状态列。文件只在本地浏览器中处理。";
    $("#restore-demo").hidden=meta.demo;
    $("#error").hidden=true;$("#error").textContent="";render();
  }
  async function handleUpload(file) {
    if(!file)return;
    try {
      const parsed=await parseUpload(file);
      setDataset(parsed.rows,{demo:false,filename:file.name,fields:parsed.fields,headers:parsed.inputHeaders});
    } catch(error) { $("#error").hidden=false;$("#error").textContent=`无法分析该文件：${error.message}`; }
    finally { $("#order-upload").value=""; }
  }
  function asNum(v) { if (v == null || String(v).trim() === "") return NaN; return Number(String(v).replace(/[¥￥$€£,元天\s]/g, "")); }
  function asDate(v) {
    if (typeof v === "number" && v > 40000 && v < 60000) return new Date(Date.UTC(1899,11,30) + Math.floor(v)*86400000);
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
    const seenIds = new Set(), seenRows = new Set();
    const cleaned = [];
    for (const [index, raw] of rows.entries()) {
      const id = raw["订单号"] || `导入行-${index+1}`;
      const fingerprint=JSON.stringify(raw);
      if ((datasetMeta.demo&&seenIds.has(id))||(!datasetMeta.demo&&seenRows.has(fingerprint))) continue;
      seenIds.add(id);seenRows.add(fingerprint);
      const price = asNum(raw["单价"]), quantity = asNum(raw["数量"]), suppliedAmount=asNum(raw["金额"]);
      const amount = Number.isFinite(price)&&Number.isFinite(quantity)?price*quantity:suppliedAmount;
      cleaned.push({ ...raw, "订单号":id, price, quantity, amount, date: asDate(raw["日期"]), shipDate: asDate(raw["发货时间"]), signDate: asDate(raw["签收时间"]), shipPromise: asNum(raw["承诺发货时效"]), deliveryPromise: asNum(raw["承诺送达时效"]), channel: raw["渠道"] || "未知", sku: raw["商品ID"] || "未知", product: raw["商品名称"] || (datasetMeta.demo?"未知":"未提供商品名称"), category: raw["商品品类"] || (datasetMeta.demo?"未知":"未提供品类"), user: raw["用户ID"] || "未知", status: raw["订单状态"] || "未知" });
    }
    return cleaned;
  }
  function rawQuality(rows) {
    const unique = new Set(), seenIds = new Set(), seenRows = new Set(); let duplicates=0, missingDates=0, missingPrice=0, missingQty=0, zeroQty=0, negativeQty=0, missingAmount=0, mismatches=0, missingChannel=0, missingSku=0, missingUser=0;
    for (const r of rows) {
      const id=String(r["订单号"]??"");unique.add(id);
      const fingerprint=JSON.stringify(r);
      if((datasetMeta.demo&&seenIds.has(id))||(!datasetMeta.demo&&seenRows.has(fingerprint)))duplicates++;
      seenIds.add(id);seenRows.add(fingerprint);
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
    return { rows:rows.length, unique:unique.size, duplicates, missingDates, missingPrice, missingQty, zeroQty, negativeQty, missingAmount, mismatches, missingChannel, missingSku, missingUser };
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
  function valid(rows) { return rows.filter(o=>!['已退款','已取消','待付款'].includes(o.status)&&Number.isFinite(o.amount)); }
  function aggregate(rows) {
    const good=valid(rows), gmv=sum(good,"amount"), orderCount=new Set(rows.map(o=>o["订单号"])).size, goodOrderCount=new Set(good.map(o=>o["订单号"])).size, refundOrderCount=new Set(rows.filter(o=>o.status==="已退款").map(o=>o["订单号"])).size;
    const channels=group(good,o=>o.channel);
    const monthly=group(good.filter(o=>o.date),o=>month(o.date));
    const categories=group(good,o=>o.category);
    const skuMap=new Map();
    for(const o of good){const key=o.product.replace(/\s+/g,"").toLowerCase();const x=skuMap.get(key)||{name:o.product,gmv:0,orders:0,quantity:0,ids:new Set()};x.gmv+=o.amount;x.quantity+=Number(o.quantity)||0;x.ids.add(o["订单号"]);x.orders=x.ids.size;skuMap.set(key,x);}
    const topProducts=[...skuMap.values()].sort((a,b)=>b.gmv-a.gmv).slice(0,15);
    const refund=rows.filter(o=>o.status==="已退款"), refundAmount=refund.reduce((a,o)=>a+Math.abs(o.amount||0),0);
    const byChannel=[...new Set(rows.map(o=>o.channel))].map(name=>{const cr=rows.filter(o=>o.channel===name);const rr=cr.filter(o=>o.status==="已退款");const channelOrders=new Set(cr.map(o=>o["订单号"])),channelRefunds=new Set(rr.map(o=>o["订单号"]));return {name,gmv:sum(good.filter(o=>o.channel===name),"amount"),orders:channelOrders.size,refunds:channelRefunds.size,refundRate:ratio(channelRefunds.size,channelOrders.size),refundAmount:rr.reduce((s,o)=>s+Math.abs(o.amount||0),0)};}).sort((a,b)=>b.refundRate-a.refundRate);
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
    const funnel=traffic.length?["曝光数","访客数","加购数","下单数"].map((key,i)=>({name:["曝光","访客","加购","下单"][i],value:funnelRows.reduce((a,x)=>a+(Number(x[key])||0),0)})):[];
    const trafficByChannel=[...new Set(funnelRows.map(t=>t.channel))].map(name=>{const ts=funnelRows.filter(t=>t.channel===name);const fo=funnelRows.filter(t=>t.channel===name);const trafficCount=key=>fo.reduce((a,t)=>a+(Number(t[key])||0),0);const orderGmv=byChannel.find(c=>c.name===name)?.gmv||0;return {name,exposure:trafficCount("曝光数"),visitors:trafficCount("访客数"),carts:trafficCount("加购数"),orders:trafficCount("下单数"),gmv:orderGmv,visitRate:ratio(trafficCount("访客数"),trafficCount("曝光数")),cartRate:ratio(trafficCount("加购数"),trafficCount("访客数")),conversion:ratio(trafficCount("下单数"),trafficCount("访客数"))};}).sort((a,b)=>b.exposure-a.exposure);
    const catalogOnSale=products.filter(p=>p["在售状态"]==="在售"), soldIds=new Set(good.map(o=>o.sku));
    const activeSold=catalogOnSale.filter(p=>soldIds.has(p["商品ID"])).length;
    const reasons=group(refund,o=>o["退款原因"],"one");
    for(const r of reasons) r.value=refund.filter(o=>(o["退款原因"]||"未知")===r.name).length;
    return {rows,good,gmv,orderCount,goodOrderCount,refundOrderCount,channels,monthly,categories,topProducts,refund,refundAmount,byChannel,customers:customerRows,segments:[...segs.values()].sort((a,b)=>b.gmv-a.gmv),repeatCustomers:customerRows.filter(x=>x.frequency>=2).length,customerGmv:customerRows.reduce((a,x)=>a+x.gmv,0),customerOrderCount:customerRows.reduce((a,x)=>a+x.frequency,0),topCustomers:[...customerRows].sort((a,b)=>b.gmv-a.gmv).slice(0,Math.max(1,roundTiesToEven(customerRows.length*.1))),shipped,shipLag,late,delivered,deliveryLag,overdue,funnel,trafficByChannel,catalogOnSale,activeSold,reasons};
  }
  function barPanel(title, rows, format=(x)=>num(x), options={}) {
    if(!rows.length) return panel(title,'<div class="empty">当前筛选下暂无可用数据</div>',options);
    const max=Math.max(...rows.map(x=>x.value),1), limit=options.limit||rows.length;
    const body=rows.slice(0,limit).map((x,i)=>{const formatted=String(format(x.value,x)),parts=formatted.split(" · 累计 "),share=x.value/max*100;return `<div class="bar-row"><span class="bar-label" title="${safe(x.name)}">${safe(x.name)}</span><span class="bar-track" role="img" aria-label="${safe(x.name)}：${safe(formatted)}，为同图最大值的 ${pct(share/100)}"><span class="bar-fill" style="display:block;width:${Math.max(1,share)}%;--bar-color:${COLORS[i%COLORS.length]}"></span></span><span class="bar-value"><strong>${safe(parts[0])}</strong>${parts[1]?`<small>累计 ${safe(parts[1])}</small>`:""}</span></div>`;}).join("");
    return panel(title,`<div class="chart-bars">${body}</div><div class="chart-axis"><span>0</span><span>25%</span><span>50%</span><span>75%</span><span>100% · 同图最大值</span></div>`,options);
  }
  function insightPanel(title, headline, detail, options={}) {
    return panel(title,`<div class="insight-callout"><span class="insight-mark" aria-hidden="true">✦</span><div><strong>${headline}</strong><p>${detail}</p></div></div>`,options);
  }
  function donutPanel(title, rows, options={}) {
    const ranked=rows.filter(x=>Number(x.value)>0).sort((a,b)=>Number(b.value)-Number(a.value));
    const usable=ranked.length>6?[...ranked.slice(0,5),{name:"其他",value:ranked.slice(5).reduce((s,x)=>s+Number(x.value),0)}]:ranked;
    const total=usable.reduce((s,x)=>s+Number(x.value),0);
    if(!total)return panel(title,'<div class="empty">当前筛选下暂无可用数据</div>',options);
    let edge=0;
    const stops=usable.map((x,i)=>{const start=edge;edge+=Number(x.value)/total*100;return `${COLORS[i%COLORS.length]} ${start.toFixed(2)}% ${edge.toFixed(2)}%`;}).join(",");
    const legend=usable.map((x,i)=>`<div class="donut-legend-row"><span class="donut-dot" style="--donut-color:${COLORS[i%COLORS.length]}"></span><span class="donut-name" title="${safe(x.name)}">${safe(x.name)}</span><strong>${pct(Number(x.value)/total)}</strong><small>${safe(money(Number(x.value)))}</small></div>`).join("");
    const body=`<div class="donut-layout"><div class="donut" role="img" aria-label="${safe(title)}，总额 ${safe(money(total))}" style="--donut-stops:${stops}"><div><strong>${safe(money(total))}</strong><span>合计金额</span></div></div><div class="donut-legend">${legend}</div></div>`;
    return panel(title,body,options);
  }
  function panel(title,body,options={}) {return `<article class="panel ${options.wide?'wide':''}"><div class="panel-heading"><div><h2>${title}</h2>${options.note?`<p>${options.note}</p>`:""}</div>${options.tag?`<span class="panel-tag">${options.tag}</span>`:""}</div>${body}${options.definition?`<p class="definition">${options.definition}</p>`:""}</article>`;}
  function table(headers, rows) {return `<div class="table-wrap"><table><thead><tr>${headers.map(h=>`<th>${safe(h)}</th>`).join("")}</tr></thead><tbody>${rows.length?rows.map(r=>`<tr>${r.map(c=>`<td>${c}</td>`).join("")}</tr>`).join(""):`<tr><td colspan="${headers.length}">暂无数据</td></tr>`}</tbody></table></div>`;}
  function trendPanel(rows) {
    if(!rows.length)return panel("月度 GMV 趋势",'<div class="empty">当前筛选下暂无可用数据</div>');
    rows=[...rows].sort((a,b)=>a.name.localeCompare(b.name));
    const w=720,h=230,pad={l:68,r:16,t:18,b:34};const values=rows.map(x=>x.value);const max=Math.max(...values,1),topTick=Math.ceil(max/4);const points=rows.map((x,i)=>{const px=pad.l+(rows.length===1?0:i*(w-pad.l-pad.r)/(rows.length-1));const py=pad.t+(h-pad.t-pad.b)*(1-x.value/(topTick*4));return [px,py,x];});const path=points.map((p,i)=>`${i?'L':'M'}${p[0]},${p[1]}`).join(' ');const poly=`${pad.l},${h-pad.b} ${points.map(p=>`${p[0]},${p[1]}`).join(' ')} ${w-pad.r},${h-pad.b}`;
    const labels=rows.map((x,i)=>i%Math.ceil(rows.length/8)===0||i===rows.length-1?`<text x="${points[i][0]}" y="${h-8}" text-anchor="middle" class="trend-label">${safe(x.name.slice(5))}月</text>`:"").join("");const dots=points.map(p=>`<circle cx="${p[0]}" cy="${p[1]}" r="4" class="trend-point"><title>${safe(p[2].name)} · ${money(p[2].value)}</title></circle>`).join("");const grid=Array.from({length:5},(_,i)=>{const y=pad.t+(h-pad.t-pad.b)*i/4;return `<line x1="${pad.l}" y1="${y}" x2="${w-pad.r}" y2="${y}" class="trend-grid"/><text x="${pad.l-10}" y="${y+4}" text-anchor="end" class="trend-axis-label">${money(topTick*(4-i))}</text>`;}).join("");
    return panel("月度有效 GMV 趋势",`<svg class="trend" viewBox="0 0 ${w} ${h}" role="img" aria-label="月度 GMV 折线图，纵轴金额，横轴月份"><defs><linearGradient id="trendFill" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#3889e5" stop-opacity=".18"/><stop offset="1" stop-color="#3889e5" stop-opacity="0"/></linearGradient></defs>${grid}<polygon points="${poly}" class="trend-area"/><path d="${path}" class="trend-line"/>${dots}${labels}</svg><div class="legend"><span><i></i>有效 GMV（元）</span><span>按下单日期汇总</span></div>`,{note:"纵轴为 GMV 金额，横轴为月份；未标注日期的订单不进入趋势图。"});
  }
  function kpis(a) {
    const gmvValue=a.gmv>=100000?`¥${(a.gmv/10000).toLocaleString("zh-CN",{maximumFractionDigits:1})}万`:money(a.gmv);
    const hasStatus=datasetMeta.demo||datasetMeta.fields.includes("订单状态"), hasQuantity=datasetMeta.demo||datasetMeta.fields.includes("数量");
    const values=[[hasStatus?"有效 GMV":"订单金额合计",gmvValue,hasStatus?"排除退款、取消与待付款":"未提供状态，未排除退款/取消/待付款","¥"],[hasStatus?"有效订单":"订单数",num(a.goodOrderCount),hasStatus?"按订单号去重":"按订单号去重；未排除无效状态","▤"],["客单价",money(ratio(a.gmv,a.goodOrderCount)),"金额合计 ÷ 订单数","↗"],[hasQuantity?"有效商品件数":"商品件数",hasQuantity?num(sum(a.good,"quantity")):"—",hasQuantity?"有效订单商品数量":"未提供商品数量","▧"],["退款率",hasStatus?pct(ratio(a.refundOrderCount,a.orderCount)):"—",hasStatus?"退款订单 ÷ 全量订单":"未提供订单状态","↻"]];
    $("#kpis").innerHTML=values.map(([label,value,note,glyph])=>`<article class="kpi-card"><div class="kpi-top"><span>${label}</span><span class="kpi-glyph">${glyph}</span></div><div class="kpi-value">${value}</div><div class="kpi-note">${note}</div></article>`).join("");
  }
  function overview(a) {
    const cumulative=[];let acc=0;const top=a.topProducts.map(x=>{acc+=x.gmv;return {name:x.name,value:x.gmv,share:acc/a.gmv};});
    const rows=a.channels.map(x=>({name:x.name,value:x.value}));
    const peak=a.monthly.slice().sort((x,y)=>y.value-x.value)[0], channel=a.channels[0], share=channel?ratio(channel.value,a.gmv):0;
    const headline=channel?`${safe(channel.name)}贡献最高，占有效 GMV ${pct(share)}`:"当前筛选范围暂无 GMV 数据";
    const detail=peak?`最高月份为 ${safe(peak.name)}（${money(peak.value)}）。下方可查看月度趋势、渠道结构和商品排行。`:"选择包含订单金额的日期范围后查看趋势。";
    return insightPanel("经营重点",headline,detail,{wide:true})+trendPanel(a.monthly)+donutPanel("渠道 GMV 占比",rows,money,{note:"按有效 GMV 汇总；占比用于描述结构，不代表渠道投放效果。"})+barPanel("商品 GMV 排名 · TOP 15",top,(v,x)=>`${money(v)} · 累计 ${pct(x.share)}`,{wide:true,note:"商品名称按 GMV 排序；累计占比帮助判断销售集中度。"});
  }
  function channelsPage(a) {
    const funnelRows=a.funnel.map((x,i)=>({name:x.name,value:x.value}));
    const channelRows=a.trafficByChannel.map(x=>[safe(x.name),num(x.exposure),num(x.visitors),num(x.carts),num(x.orders),pct(x.conversion),money(x.gmv)]);
    const hasTraffic=traffic.length>0;
    const convert=a.trafficByChannel.slice().sort((x,y)=>y.conversion-x.conversion)[0];
    const takeaway=hasTraffic?(convert?`${safe(convert.name)}下单转化率最高，为 ${pct(convert.conversion)}`:"当前筛选无可比较的渠道转化率"):"当前文件没有流量表，无法计算转化率";
    return insightPanel("渠道观察",takeaway,hasTraffic?"漏斗来自配套流量表；成交金额按有效订单统计。":"可上传按日期和渠道汇总的曝光、访客、加购数据补充分析。",{wide:true})+barPanel("流量转化漏斗",hasTraffic?funnelRows:[],num,{wide:true,note:hasTraffic?"曝光、访客、加购来自配套流量表；下单数由订单明细回填。":"上传文件没有流量表，不能计算曝光、访客、加购和下单转化率。",definition:hasTraffic?"访客率 = 访客 ÷ 曝光；加购率 = 加购 ÷ 访客；下单转化率 = 下单 ÷ 访客。":"如需流量转化分析，请同时提供按日期和渠道汇总的流量表。"})+donutPanel("渠道 GMV 结构",a.channels.map(x=>({name:x.name,value:x.value})),{note:"渠道 GMV 占比。金额按有效订单口径统计。"})+panel("渠道流量与成交明细",`<details class="inline-details"><summary>展开查看 ${num(channelRows.length)} 个渠道的完整数据</summary>${table(["渠道","曝光","访客","加购","下单","下单转化率","有效 GMV"],channelRows)}</details>`,{note:hasTraffic?"成交金额使用有效订单；流量指标来自配套流量表。":"暂无配套流量表，转化指标不可用。"})+panel("指标口径",`<div class="quality-list"><div class="quality-item"><span>流量数据来源</span><strong>${hasTraffic?"配套日 × 渠道流量表":"未提供"}</strong></div><div class="quality-item"><span>筛选口径</span><strong>日期范围与所选渠道</strong></div><div class="quality-item"><span>守恒关系</span><strong>${hasTraffic?"下单数与订单明细对齐":"无法核验"}</strong></div><div class="quality-item"><span>限制</span><strong>${datasetMeta.demo?"模拟数据，不代表真实转化水平":"仅用已上传字段，不反推流量"}</strong></div></div>`,{wide:true});
  }
  function productsPage(a) {
    if(!datasetMeta.demo&&!datasetMeta.fields.includes("商品名称")) return panel("商品分析",'<div class="empty">文件没有商品名称列，无法进行商品排行、品类和品牌分析。</div>',{wide:true,note:"若文件含商品名称/产品名称/商品标题列，请检查列名后重传。"});
    const category=a.categories.map(x=>({name:x.name,value:x.value}));
    const skus=a.topProducts.map(x=>({name:x.name,value:x.gmv}));
    const topBrand=group(a.good,o=>{const p=products.find(x=>x["商品ID"]===o.sku);return p?.["品牌"]||"未知";}).slice(0,10);
    const sellPct=ratio(a.activeSold,a.catalogOnSale.length);
    const hasCategory=datasetMeta.demo||datasetMeta.fields.includes("商品品类");
    const productsAndCategories=(hasCategory?donutPanel("品类 GMV 占比",category,{note:"按商品品类聚合有效订单金额。"}):panel("品类 GMV 结构",'<div class="empty">文件没有商品品类列，无法比较品类 GMV。</div>'))+barPanel("商品 GMV 排名 · TOP 15",skus,money,{wide:true,note:"商品名称按 GMV 排序完整展示。"});
    return productsAndCategories+(products.length?barPanel("品牌 GMV TOP 10",topBrand,money,{note:"品牌通过商品主数据表匹配。"}):panel("品牌 GMV TOP 10",'<div class="empty">未提供商品目录，无法可靠识别品牌。</div>',{note:"不会仅凭商品名称猜测品牌。"}))+panel("商品动销",`<div class="stat-strip"><div class="stat-box"><span>在售 SKU（目录）</span><strong>${num(a.catalogOnSale.length)}</strong></div><div class="stat-box"><span>有销量 SKU</span><strong>${num(a.activeSold)}</strong></div><div class="stat-box"><span>动销率</span><strong>${products.length?pct(sellPct):"—"}</strong></div><div class="stat-box"><span>未动销 SKU</span><strong>${products.length?num(Math.max(0,a.catalogOnSale.length-a.activeSold)):"—"}</strong></div></div>${products.length?`<div class="progress-track"><span style="width:${Math.max(0,Math.min(100,sellPct*100))}%"></span></div>`:""}<p class="definition">${products.length?"动销率 = 有销量的在售 SKU ÷ 商品目录中的在售 SKU。":"未提供商品目录，动销率不可计算。"}</p>`,{wide:true});
  }
  function usersPage(a) {
    if(!datasetMeta.demo&&!datasetMeta.fields.includes("用户ID")) return panel("用户 / RFM 分析",'<div class="empty">文件没有用户标识列，无法计算复购率、客户价值和 RFM 分层。</div>',{wide:true,note:"若文件含用户ID/客户ID/买家ID列，请检查列名后重传。"});
    const gmv= a.customerGmv, rfmGmv=a.segments.reduce((s,x)=>s+x.gmv,0);
    const repeat=a.repeatCustomers, cust=a.customers.length;
    const topShare=ratio(a.topCustomers.reduce((s,x)=>s+x.gmv,0),a.gmv);
    return panel("用户复购与价值概况",`<div class="stat-strip"><div class="stat-box"><span>有效客户</span><strong>${num(cust)}</strong></div><div class="stat-box"><span>复购客户</span><strong>${num(repeat)}</strong></div><div class="stat-box"><span>复购率</span><strong>${pct(ratio(repeat,cust))}</strong></div><div class="stat-box"><span>客均有效订单</span><strong>${num(ratio(a.customerOrderCount,cust))}</strong></div></div><p class="definition">复购客户为观察窗口内有效订单数 ≥ 2 的已知用户。未合并同一自然人的多账号。</p>`,{wide:true})+barPanel("RFM 分层客户数",a.segments.map(x=>({name:x.name,value:x.customers})),num,{note:"按当前文件观察窗口划分，显示各层级客户数量。"})+donutPanel("RFM 分层 GMV 占比",a.segments.map(x=>({name:x.name,value:x.gmv})),{note:"各分层客户贡献的有效 GMV。"})+barPanel("用户 GMV 集中度",[{name:`GMV 前 10% 用户（${a.topCustomers.length} 人）`,value:(topShare||0)*100}],v=>pct(v/100),{note:"用于观察用户贡献集中程度，不代表未来价值。"})+panel("分析边界",`<details class="inline-details"><summary>查看 RFM 与用户统计口径</summary><div class="quality-list"><div class="quality-item"><span>客户标识</span><strong>${datasetMeta.demo?"模拟用户 ID":"上传文件中的用户标识"}</strong></div><div class="quality-item"><span>历史窗口</span><strong>仅含当前数据区间</strong></div><div class="quality-item"><span>新客定义</span><strong>无法区分窗口前老客</strong></div><div class="quality-item"><span>数据性质</span><strong>${datasetMeta.demo?"合成练习数据":"用户上传文件"}</strong></div></div></details>`,{wide:true});
  }
  function fulfilmentPage(a) {
    const reasons=a.reasons.map(x=>({name:x.name,value:x.value}));
    const lateRate=ratio(a.late.length,a.shipLag.length), overdueRate=ratio(a.overdue.length,a.deliveryLag.length), avgShip=ratio(a.shipLag.reduce((s,x)=>s+x.days,0),a.shipLag.length), avgDelivery=ratio(a.deliveryLag.reduce((s,x)=>s+x.days,0),a.deliveryLag.length);
    const hasStatus=datasetMeta.demo||datasetMeta.fields.includes("订单状态"), canShipTime=datasetMeta.demo||["日期","发货时间","承诺发货时效"].every(x=>datasetMeta.fields.includes(x)), canDeliveryTime=datasetMeta.demo||["发货时间","签收时间","承诺送达时效"].every(x=>datasetMeta.fields.includes(x));
    const byChannel=a.byChannel.map(x=>[safe(x.name),num(x.orders),hasStatus?num(x.refunds):"—",hasStatus?pct(x.refundRate):"—",hasStatus?money(x.refundAmount||0):"—"]);
    const fulfilmentAvailable=(canShipTime&&a.shipped.length>0)||(canDeliveryTime&&a.delivered.length>0);
    const fulfilmentContent=fulfilmentAvailable?`<div class="stat-strip"><div class="stat-box"><span>已发货订单</span><strong>${canShipTime?num(a.shipLag.length):"—"}</strong></div><div class="stat-box"><span>平均发货时效</span><strong>${canShipTime?`${num(avgShip)} 天`:"—"}</strong></div><div class="stat-box"><span>迟发率</span><strong>${canShipTime?pct(lateRate):"—"}</strong></div><div class="stat-box"><span>签收订单 · 逾期率</span><strong>${canDeliveryTime?`${num(a.deliveryLag.length)} · ${pct(overdueRate)}`:"—"}</strong></div></div>`:`<div class="empty">${datasetMeta.demo?"当前筛选下暂无发货/签收记录":"缺少实际发货/签收时间或对应承诺时效列，履约时效不可计算。"}</div>`;
    return panel("退款指标 · 全量订单口径",hasStatus?`<div class="stat-strip"><div class="stat-box"><span>全量订单</span><strong>${num(a.orderCount)}</strong></div><div class="stat-box"><span>退款订单</span><strong>${num(a.refundOrderCount)}</strong></div><div class="stat-box"><span>退款率</span><strong>${pct(ratio(a.refundOrderCount,a.orderCount))}</strong></div><div class="stat-box"><span>退款金额（绝对值）</span><strong>${money(a.refundAmount)}</strong></div></div><details class="inline-details"><summary>展开查看渠道退款明细</summary>${table(["渠道","全量订单","退款订单","退款率","退款金额"],byChannel)}</details><p class="definition">退款率 = 退款订单 ÷ 全量订单；核心 GMV 指标排除退款订单，两种分母不可混用。</p>`:'<div class="empty">文件没有可识别的订单状态列，无法区分退款订单，退款金额和退款率不可用。</div>',{wide:true})+(hasStatus?barPanel("退款原因",reasons,num,{note:"退款原因使用订单文件中的对应字段。"}):"")+panel("履约时效与异常",fulfilmentContent,{note:"迟发率和逾期率需要实际时间与对应承诺时效列。"});
  }
  function qualityPage(a) {
    const q=rawProfile;
    const pairs=[["原始明细行",q.rows],["唯一订单号数",q.unique],[datasetMeta.demo?"重复订单号记录":"完全重复明细行",q.duplicates],["日期缺失或无法解析",q.missingDates],["单价缺失 / 无法解析",q.missingPrice],["数量缺失",q.missingQty],["数量为 0",q.zeroQty],["负数量（退款记录）",q.negativeQty],["金额缺失",q.missingAmount],["金额与单价 × 数量不一致",q.mismatches],["渠道缺失",q.missingChannel],["商品 ID 缺失",q.missingSku],["用户 ID 缺失",q.missingUser]];
    const cells=pairs.map(([label,value])=>`<div class="quality-item"><span>${label}</span><strong>${num(value)} <small>(${pct(ratio(value,q.rows))})</small></strong></div>`).join("");
    const issues=[ ["重复记录",q.duplicates], ["缺失日期",q.missingDates], ["缺失金额",q.missingAmount], ["金额不一致",q.mismatches], ["缺失商品ID",q.missingSku] ].map(([name,value])=>({name,value}));
    return barPanel("主要数据质量问题",issues,num,{note:"条形长度按问题行数比较；问题之间可能重叠，不可相加作为总问题数。"})+panel("原始数据体检",`<details class="inline-details"><summary>展开查看 ${pairs.length} 项数据质量计数</summary><div class="quality-list">${cells}</div></details>`,{wide:true,note:`质量计数基于 ${num(q.rows)} 行原始记录；有效订单按订单号去重。`})+panel("关键指标定义",`<details class="inline-details"><summary>查看主要指标的计算口径</summary>${table(["指标","计算口径","使用范围"],[["有效 GMV","有效订单金额之和","排除退款、取消和待付款状态"],["客单价","有效 GMV ÷ 有效订单数","与有效订单号数同一分母"],["退款率","退款订单 ÷ 全量订单","退款与履约页面"],["下单转化率","流量表下单数 ÷ 访客数","只使用配套流量表"],["动销率","有销量在售 SKU ÷ 在售 SKU","分母来自商品目录"],["迟发率","超时发货订单 ÷ 已发货订单","不含待发货订单"]])}</details>`,{wide:true,note:"缺少对应字段时不推算或填补业务指标。"})+panel("分析校验",`<div class="quality-list"><div class="quality-item"><span>订单粒度</span><strong>金额按明细行加总，订单数按订单号去重</strong></div><div class="quality-item"><span>数据可追溯</span><strong>原始行 + 清洗后明细</strong></div><div class="quality-item"><span>流量转化来源</span><strong>${traffic.length?"配套流量表":"未提供"}</strong></div><div class="quality-item"><span>动销率分母来源</span><strong>${products.length?"商品目录":"未提供"}</strong></div></div>`,{wide:true});
  }
  function reportPage(a) {
    const channel=a.channels[0], category=a.categories[0], hasStatus=datasetMeta.demo||datasetMeta.fields.includes("订单状态"), hasUser=datasetMeta.demo||datasetMeta.fields.includes("用户ID"), hasCategory=datasetMeta.demo||datasetMeta.fields.includes("商品品类"), refundRate=ratio(a.refundOrderCount,a.orderCount), repeatRate=hasUser?ratio(a.repeatCustomers,a.customers.length):null, lateRate=ratio(a.late.length,a.shipped.length), overdueRate=ratio(a.overdue.length,a.delivered.length);
    const start=$("#date-start").value||"未设", end=$("#date-end").value||"未设", selected=[...document.querySelectorAll("#channel-options input:checked")].map(x=>x.value);
    const canShipTime=datasetMeta.demo||["日期","发货时间","承诺发货时效"].every(x=>datasetMeta.fields.includes(x)), canDeliveryTime=datasetMeta.demo||["发货时间","签收时间","承诺送达时效"].every(x=>datasetMeta.fields.includes(x));
    const limitations=datasetMeta.demo?["数据属性：所有表均为固定种子生成的模拟数据，不代表真实企业表现。"]:[`数据来源：浏览器本地文件 ${datasetMeta.filename}，不会上传服务器。`,...(datasetMeta.fields.includes("日期")?[]:["未识别日期列，月度趋势和日期筛选不适用。"]),...(datasetMeta.fields.includes("订单状态")?[]:["未识别订单状态列，金额合计未排除退款或取消订单。"]),...(datasetMeta.fields.includes("渠道")?[]:["未识别渠道列，渠道分析归为“未知”。"]),...(hasCategory?[]:["未提供商品品类，品类分析不可用。"]),...(hasUser?[]:["未提供用户标识，复购和 RFM 分析不可用。"]),...(canShipTime?[]:["未提供实际发货时间或承诺发货时效，迟发分析不可用。"]),...(canDeliveryTime?[]:["未提供实际签收时间或承诺送达时效，逾期分析不可用。"]),"未上传流量表和商品目录，流量转化、品牌及动销率不可用。"];
    const observations=[
      ["经营规模",`筛选范围内共有 ${num(a.orderCount)} 笔去重订单，其中 ${num(a.goodOrderCount)} 笔纳入金额统计；${hasStatus?"有效 GMV":"订单金额合计"}为 ${money(a.gmv)}，客单价为 ${money(ratio(a.gmv,a.goodOrderCount))}。`],
      ["渠道贡献",channel?`${safe(channel.name)}渠道的有效 GMV 最高，为 ${money(channel.value)}，占当前有效 GMV ${pct(ratio(channel.value,a.gmv))}。这是贡献结构描述，不代表渠道投放效果。`:"当前筛选范围暂无渠道 GMV 可比较。"],
      ["商品结构",hasCategory&&category?`${safe(category.name)}品类 GMV 最高，为 ${money(category.value)}，占比 ${pct(ratio(category.value,a.gmv))}；TOP 3 品类合计占 ${pct(ratio(a.categories.slice(0,3).reduce((s,x)=>s+x.value,0),a.gmv))}。`:hasCategory?"当前筛选范围暂无品类 GMV 可比较。":"未提供商品品类，无法比较品类结构。"],
      ["用户与履约",`${hasUser?`已知用户复购率为 ${pct(repeatRate)}`:"未提供用户标识，无法计算复购率"}；${canShipTime?`迟发率为 ${pct(lateRate)}`:"缺少发货时效字段，无法计算迟发率"}；${canDeliveryTime?`签收逾期率为 ${pct(overdueRate)}`:"缺少签收时效字段，无法计算逾期率"}。`],
    ];
    const cards=observations.map(([title,text],i)=>`<article class="report-insight"><span class="report-index">0${i+1}</span><div><h3>${title}</h3><p>${text}</p></div></article>`).join("");
    const metricCards=[[hasStatus?"有效 GMV":"订单金额合计",money(a.gmv)],["有效订单",num(a.goodOrderCount)],["客单价",money(ratio(a.gmv,a.goodOrderCount))],["退款率",hasStatus?pct(refundRate):"—"],["复购率",hasUser?pct(repeatRate):"—"]].map(([label,value])=>`<div class="report-kpi"><span>${label}</span><strong>${value}</strong></div>`).join("");
    return panel("执行摘要",`<div class="report-scope"><span><b>日期范围</b>${safe(start)} 至 ${safe(end)}</span><span><b>所选渠道</b>${selected.length?safe(selected.join("、")):"未选择"}</span><span><b>筛选订单</b>${num(a.orderCount)} 笔</span></div><div class="report-kpis">${metricCards}</div><div class="report-insights">${cards}</div>`,{wide:true,note:"结论随上方筛选更新，只呈现当前文件字段可支持的观察结果。"})+
      donutPanel("渠道 GMV 结构",a.channels.map(x=>({name:x.name,value:x.value})),{note:"帮助快速比较收入来源；不代表渠道投放效果。"})+donutPanel("品类 GMV 结构",a.categories,{note:"仅使用文件提供的品类字段。"})+
      panel("数据限制与口径",`<details class="inline-details"><summary>展开查看 ${limitations.length+2} 项数据说明</summary><ul class="report-actions">${limitations.map(x=>`<li>${safe(x)}</li>`).join("")}<li>订单金额按有效明细行求和，订单数按订单号去重；请确认源表每行的金额粒度，避免重复汇总订单总额。</li><li>当前结果为描述性统计，不推断利润、ROI 或因果效果。</li></ul></details>`,{wide:true,note:"缺少的业务字段会明确列出，不会用模拟值补齐用户上传的数据。"});
  }
  function renderDetails(rows) {
    const cols=["订单号","日期","渠道","商品名称","商品品类","数量","金额","用户ID","订单状态"];
    const display=[...rows].sort((a,b)=>(b.date?.getTime()||0)-(a.date?.getTime()||0));
    $("#detail-count").textContent=`${num(rows.length)} 行 · 当前展示 ${Math.min(500,display.length)} 行`;
    $("#detail-table").innerHTML=`<thead><tr>${cols.map(c=>`<th>${safe(c)}</th>`).join("")}</tr></thead><tbody>${display.slice(0,500).map(o=>`<tr>${[o["订单号"],o["日期"],o.channel,o.product,o.category,Number.isFinite(o.quantity)?num(o.quantity):"—",Number.isFinite(o.amount)?money(o.amount):"—",o.user,o.status].map(x=>`<td>${safe(x)}</td>`).join("")}</tr>`).join("")}</tbody>`;
  }
  function render() {
    const rows=filtered();const a=aggregate(rows);const [title,desc]=PAGE_INFO[page];
    $("#page-name").textContent=title;$("#page-title").textContent=title;$("#page-desc").textContent=desc;
    $("#upload-card").hidden=page!=="overview";
    document.querySelectorAll(".nav-item").forEach(b=>b.classList.toggle("active",b.dataset.page===page));
    $("#kpis").hidden=page!=="overview";
    kpis(a);
    const renderers={overview,channels:channelsPage,products:productsPage,users:usersPage,fulfilment:fulfilmentPage,quality:qualityPage,report:reportPage};
    $("#page-content").innerHTML=renderers[page](a);
    renderDetails(rows);
    window.currentDashboard={a,rows};
  }
  function download(name,text,type="text/plain;charset=utf-8") {const blob=new Blob(["\uFEFF",text],{type});const url=URL.createObjectURL(blob);const a=document.createElement("a");a.href=url;a.download=name;a.click();URL.revokeObjectURL(url);}
  function downloadOrders() {const {rows}=window.currentDashboard;const headers=["订单号","日期","渠道","商品ID","商品名称","单价","数量","金额","用户ID","收货省份","订单状态","商品品类","承诺发货时效","物流商","承诺送达时效","发货时间","签收时间","退款原因"];const quote=x=>`"${String(x??"").replace(/"/g,'""')}"`;const lines=[headers.map(quote).join(","),...rows.map(o=>headers.map(h=>quote(o[h])).join(","))];download("ecommerce-filtered-orders.csv",lines.join("\r\n"),"text/csv;charset=utf-8");}
  function downloadSummary() {
    const {a}=window.currentDashboard,hasStatus=datasetMeta.demo||datasetMeta.fields.includes("订单状态");
    const limitations=datasetMeta.demo?["订单、流量和商品目录为固定种子生成的模拟数据。"]:[`数据源为 ${datasetMeta.filename}，文件仅在浏览器本地处理。`,...(traffic.length?[]:["没有流量表，转化率不可用。"]),...(products.length?[]:["没有商品目录，品牌及动销率不可用。"]),...(datasetMeta.fields.includes("用户ID")?[]:["没有用户标识，复购与 RFM 不可用。"]),...(hasStatus?[]:["没有订单状态，金额合计未排除退款和取消订单。"])];
    const out={data_source:datasetMeta.demo?"synthetic_demo":datasetMeta.filename,filters:{start:$("#date-start").value||null,end:$("#date-end").value||null,channels:[...document.querySelectorAll("#channel-options input:checked")].map(x=>x.value)},kpi:{raw_rows:rawProfile.rows,filtered_unique_orders:a.orderCount,valid_orders:a.goodOrderCount,valid_gmv:Number(a.gmv.toFixed(2)),aov:Number((ratio(a.gmv,a.goodOrderCount)||0).toFixed(2)),refund_orders:a.refundOrderCount,refund_rate:hasStatus?ratio(a.refundOrderCount,a.orderCount):null},channel:a.byChannel,traffic_funnel:a.funnel,product_top15:a.topProducts.map(x=>({product:x.name,gmv:Number(x.gmv.toFixed(2))})),rfm:a.segments,fulfilment:{shipped_orders:a.shipped.length,late_orders:a.late.length,late_rate:ratio(a.late.length,a.shipped.length),delivered_orders:a.delivered.length,overdue_orders:a.overdue.length,overdue_rate:ratio(a.overdue.length,a.delivered.length)},limitations};
    download("ecommerce-analysis-summary.json",JSON.stringify(out,null,2),"application/json;charset=utf-8");
  }
  async function start() {
    try {
      const [raw,trafficRows,catalogRows]=await Promise.all([loadCSV("portfolio_demo/synthetic_orders.csv"),loadCSV("portfolio_demo/synthetic_traffic.csv"),loadCSV("portfolio_demo/synthetic_products.csv")]);
      sampleData={raw,trafficRows,catalogRows};
      document.querySelectorAll(".nav-item").forEach(b=>b.addEventListener("click",()=>{page=b.dataset.page;render();window.scrollTo({top:0,behavior:"smooth"});}));
      $("#channel-options").addEventListener("change",render);$("#date-start").addEventListener("change",render);$("#date-end").addEventListener("change",render);
      $("#reset-filter").addEventListener("click",()=>{document.querySelectorAll("#channel-options input").forEach(x=>x.checked=true);$("#date-start").value=dateBounds[0];$("#date-end").value=dateBounds[1];render();});
      $("#order-upload").addEventListener("change",event=>handleUpload(event.target.files?.[0]));
      $("#restore-demo").addEventListener("click",()=>setDataset(sampleData.raw,{demo:true,filename:"",fields:[]},sampleData.trafficRows,sampleData.catalogRows));
      const uploadCard=$("#upload-card");
      uploadCard.addEventListener("dragover",event=>{event.preventDefault();uploadCard.classList.add("is-dragover");});
      uploadCard.addEventListener("dragleave",event=>{if(!uploadCard.contains(event.relatedTarget))uploadCard.classList.remove("is-dragover");});
      uploadCard.addEventListener("drop",event=>{event.preventDefault();uploadCard.classList.remove("is-dragover");handleUpload(event.dataTransfer?.files?.[0]);});
      uploadCard.addEventListener("click",event=>{if(!event.target.closest("button,a,label,input"))$("#order-upload").click();});
      uploadCard.addEventListener("keydown",event=>{if((event.key==="Enter"||event.key===" ")&&!event.target.closest("button,a,label,input")){event.preventDefault();$("#order-upload").click();}});
      $("#download-orders").addEventListener("click",downloadOrders);$("#download-summary").addEventListener("click",downloadSummary);
      setDataset(raw,{demo:true,filename:"",fields:[]},trafficRows,catalogRows);
    } catch(error) {$("#error").hidden=false;$("#error").textContent=`Demo 加载失败：${error.message}。请从 GitHub Pages 站点打开，不要直接双击 index.html。`;$("#kpis").innerHTML="";}
  }
  start();
})();

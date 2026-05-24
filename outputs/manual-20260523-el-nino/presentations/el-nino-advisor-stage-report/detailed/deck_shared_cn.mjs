
const C = { bg:"#f7f3ea", ink:"#1d1b18", muted:"#5d574f", rule:"#d8d1c4", red:"#cc5a43", teal:"#2f6f73", blue:"#4a5f99", pale:"#fffaf1", rose:"#f5e5df", green:"#edf3ef" };
function bg(slide, ctx){ ctx.addShape(slide,{x:0,y:0,w:1280,h:720,fill:C.bg}); }
function text(slide, ctx, value, x,y,w,h,o={}){ return ctx.addText(slide,{text:value||"",x,y,w,h,fontSize:o.size||20,bold:o.bold||false,color:o.color||C.ink,typeface:o.title?ctx.fonts.title:ctx.fonts.body,valign:o.valign||"top",align:o.align||"left",insets:o.insets||{left:0,right:0,top:0,bottom:0}}); }
function header(slide,ctx,d){ text(slide,ctx,d.k,58,30,360,25,{size:14,bold:true,color:C.red}); text(slide,ctx,d.t,58,64,1100,82,{size:29,bold:true,title:true}); ctx.addShape(slide,{x:58,y:148,w:1130,h:1.5,fill:C.rule}); }
function src(slide,ctx,v){ text(slide,ctx,v||"",58,680,1120,26,{size:10.5,color:C.muted}); }
async function image(slide,ctx,p,x,y,w,h,fit="contain"){ await ctx.addImage(slide,{path:p,x,y,w,h,fit}); }
function bullets(slide,ctx,arr,x,y,w,row=58,size=17){ let yy=y; for(const b of arr||[]){ ctx.addShape(slide,{x,y:yy+9,w:7,h:7,fill:C.red,geometry:"ellipse"}); text(slide,ctx,b,x+20,yy,w-20,row-4,{size}); yy+=row; } }
function box(slide,ctx,title,body,x,y,w,h,fill){ ctx.addShape(slide,{x,y,w,h,fill,line:{style:"solid",fill:C.rule,width:0.8}}); text(slide,ctx,title,x+14,y+12,w-28,22,{size:14,bold:true,color:C.teal}); text(slide,ctx,body,x+14,y+42,w-28,h-50,{size:14.5,color:C.ink}); }
function table(slide,ctx,rows,x,y,w,rowH,opt={}){ const cols=rows[0].length; const widths=opt.widths||Array(cols).fill(w/cols); rows.forEach((r,i)=>{ let xx=x; r.forEach((cell,j)=>{ const cw=widths[j]; ctx.addShape(slide,{x:xx,y:y+i*rowH,w:cw,h:rowH,fill:i===0?C.ink:(i%2?C.pale:"#f2ecdf"),line:{style:"solid",fill:C.rule,width:0.7}}); text(slide,ctx,cell,xx+9,y+i*rowH+7,cw-18,rowH-10,{size:i===0?(opt.head||12):(opt.size||13.5),bold:i===0,color:i===0?"#fff":C.ink}); xx+=cw; }); }); }
async function renderDeckSlide(presentation,ctx,d){
 const slide=presentation.slides.add(); bg(slide,ctx);
 if(d.layout==="cover"){ text(slide,ctx,d.k,58,48,300,24,{size:14,bold:true,color:C.red}); text(slide,ctx,d.t,58,96,900,180,{size:38,bold:true,title:true}); text(slide,ctx,d.sub,60,304,960,58,{size:20,color:C.muted}); bullets(slide,ctx,d.bullets,68,410,900,56,17.5); ctx.addShape(slide,{x:1032,y:126,w:128,h:128,fill:C.red,geometry:"ellipse"}); ctx.addShape(slide,{x:1078,y:300,w:82,h:82,fill:C.teal,geometry:"ellipse"}); src(slide,ctx,d.src); return slide; }
 header(slide,ctx,d);
 if(d.layout==="text"){ ctx.addShape(slide,{x:76,y:178,w:1040,h:132,fill:C.rose,line:{style:"solid",fill:C.rule,width:1}}); text(slide,ctx,d.claim,98,202,996,92,{size:21,bold:true}); bullets(slide,ctx,d.points,92,350,980,70,18); }
 else if(d.layout==="glossary"){ table(slide,ctx,d.rows,70,174,1088,45,{widths:[145,315,628],size:12.4,head:12}); }
 else if(d.layout==="tableText"){ table(slide,ctx,d.rows,70,180,1088,d.rows.length>5?48:58,{widths:d.rows[0].length===3?[190,430,468]:[300,260,260],size:12.6,head:12}); box(slide,ctx,"Reading note",d.text,76,542,1040,106,C.green); }
 else if(d.layout==="figureExplain"){ await image(slide,ctx,d.image,60,182,600,366); const y=[168,302,436]; d.boxes.forEach((b,i)=>box(slide,ctx,b[0],b[1],694,y[i],452,118,i%2?C.green:C.rose)); }
 else if(d.layout==="twoFigureExplain"){ await image(slide,ctx,d.left,60,184,350,280); await image(slide,ctx,d.right,430,184,350,280); const y=[170,312,454]; d.boxes.forEach((b,i)=>box(slide,ctx,b[0],b[1],814,y[i],382,126,i%2?C.green:C.rose)); }
 else if(d.layout==="appendix"){ table(slide,ctx,d.rows,70,176,1088,48,{widths:d.rows[0].length===3?[170,390,528]:[255,570,263],size:12,head:12}); }
 src(slide,ctx,d.src); return slide;
}
export { renderDeckSlide };

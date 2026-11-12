/* mapa u-pin: dibujo del campus en webgl + canvas. los datos vienen de la base de datos (ver vista mapa)
   partes: utilidades, proyeccion, webgl, capa de nombres, gestos, pisos, hoja de sala, buscador,
   pines de reportes, gps, animaciones, secciones y la conexion con la app (al final). */
// lee un bloque de datos json que deja la pagina
function leerDato(id){return JSON.parse(document.getElementById(id).textContent)}
const UPIN=leerDato("d-config");

const S=leerDato("d-escena");const FLOORS_DATA=leerDato("d-pisos");const GROUPS_DATA=leerDato("d-grupos");
const glc=document.getElementById('gl'),cv=document.getElementById('cv'),ctx=cv.getContext('2d');
const reduceMotion=()=>matchMedia('(prefers-reduced-motion: reduce)').matches;
const FH=13,HK0=1.15;let HK=HK0,LA=1,FA=null;
const BH={'Casetas de seguridad':0.7,'Edificio K':6,'Edificio F':4,'Edificio A':3,'Edificio B':3,'Edificio C':2,'Edificio E':2,'Edificio L':1};
const BFLOORS={'Casetas de seguridad':[],'Edificio K':['6','5','4','3','2','1','-1','-2'],'Edificio F':['4','3','2','1','-1'],'Edificio A':['3','2','1'],'Edificio B':['2','1'],'Edificio C':['2','1'],'Edificio E':['2','1'],'Edificio L':['1']};
const COL={sala:'#FFFFFF',depto:'#E4DCF2',aula:'#FFFFFF',servicio:'#EDE6DA',cafe:'#F6DCA8',gimnasio:'#BFDCEB',casino:'#F6DCA8',restringido:'#D6D5D1',patio:'#E4E3DE',rampa:'#8E8E94',pasillo:'#F7DED0',estacionamiento:'#C9CBD2'};
const RH={patio:1,pasillo:1,rampa:1,estacionamiento:1,gimnasio:24,aula:22};
const cam={x:S.w*0.5,y:S.h*0.52,z:0.9,b:-0.5,p:0.95};let target=null;
let DARK=false;const TH={};function setTheme(d){DARK=d;Object.assign(TH,d?{clear:[0.141,0.169,0.22],top:'#5E6B83',wall:'#4B566D',ftop:'#4D596F',fwall:'#3F495C',dtop:'#3A4354',dwall:'#323A48',edge:[0.47,0.52,0.60],redge:[0.30,0.34,0.41],tree:'#3F6148',wr:0.294}:{clear:[0.933,0.929,0.91],top:'#F6F5F1',wall:'#E7E5DF',ftop:'#D6D5CF',fwall:'#B9B8B2',dtop:'#E4E3DE',dwall:'#D3D2CC',edge:[0.70,0.70,0.68],redge:[0.62,0.62,0.66],tree:'#7F9A45',wr:0.906})}setTheme(false);
let floor='ext',sel=null,selB=null,me=null,W=0,H=0,dpr=1,dirty=true,geoDirty=true;

/* ---------- utilidades ---------- */

// convierte un color "#rrggbb" a numeros entre 0 y 1 para webgl
function hex(c){const n=parseInt(c.slice(1),16);return [(n>>16)/255,(n>>8&255)/255,(n&255)/255]}

// area de un poligono (sirve para saber cual sala es mas chica)
function area(p){let a=0;for(let i=0;i<p.length;i++){const q=p[(i+1)%p.length];a+=p[i][0]*q[1]-q[0]*p[i][1]}return a/2}

// true si un punto esta dentro de un poligono (para saber que se toco)
function inPoly(pt,poly){let c=false;for(let i=0,j=poly.length-1;i<poly.length;j=i++){const a=poly[i],b=poly[j];if((a[1]>pt[1])!==(b[1]>pt[1])&&pt[0]<(b[0]-a[0])*(pt[1]-a[1])/(b[1]-a[1])+a[0])c=!c}return c}

// centro de un poligono: ahi van nombres y pines
function centroid(p){return p.reduce((a,q)=>[a[0]+q[0]/p.length,a[1]+q[1]/p.length],[0,0])}

// parte un poligono en triangulos para dibujarlo con webgl
function triangulate(pts){ // ear clipping, devuelve índices
  const n=pts.length;if(n<3)return[];const idx=[...Array(n).keys()];if(area(pts)<0)idx.reverse();const out=[];let guard=0;
  const cross=(a,b,c)=>(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]);
  while(idx.length>3&&guard++<5000){let ok=false;
    for(let i=0;i<idx.length;i++){const a=idx[(i+idx.length-1)%idx.length],b=idx[i],c=idx[(i+1)%idx.length];
      if(cross(pts[a],pts[b],pts[c])<=0)continue;let inside=false;
      for(const k of idx){if(k===a||k===b||k===c)continue;const p=pts[k];
        if(cross(pts[a],pts[b],p)>=0&&cross(pts[b],pts[c],p)>=0&&cross(pts[c],pts[a],p)>=0){inside=true;break}}
      if(inside)continue;out.push(a,b,c);idx.splice(i,1);ok=true;break}
    if(!ok)break}
  if(idx.length===3)out.push(idx[0],idx[1],idx[2]);return out}
// nombre de edificio de cada sala (si falta, por posición)
Object.values(FLOORS_DATA).forEach(rs=>rs.forEach(r=>{if(!r.building){const c=centroid(r.pts);const b=S.buildings.find(b=>inPoly(c,b.pts));r.building=b?b.name:''}}));
// árboles: fuera de los edificios y con un margen

// true si un punto esta cerca de un edificio (para no poner arboles encima)
function nearB(x,y){return S.buildings.some(b=>{if(inPoly([x,y],b.pts))return true;for(let i=0;i<b.pts.length;i++){const a=b.pts[i],c=b.pts[(i+1)%b.pts.length];
  const vx=c[0]-a[0],vy=c[1]-a[1],L=vx*vx+vy*vy||1;let t=((x-a[0])*vx+(y-a[1])*vy)/L;t=Math.max(0,Math.min(1,t));if(Math.hypot(a[0]+vx*t-x,a[1]+vy*t-y)<10)return true}return false})}
const TREES=S.trees.filter(([x,y])=>!nearB(x,y));

/* ---------- proyección (igual en js y en el shader) ---------- */

// proyeccion: pasa un punto del plano (x, y, altura) a la pantalla segun la camara
function P(x,y,z){const dx=x-cam.x,dy=y-cam.y,c=Math.cos(cam.b),s=Math.sin(cam.b);const rx=dx*c-dy*s,ry=dx*s+dy*c,h=(z||0)*HK;
  return [W/2+rx*cam.z,H*0.55+(ry*Math.cos(cam.p)-h*Math.sin(cam.p))*cam.z,ry*Math.sin(cam.p)+h*Math.cos(cam.p)]}

// lo contrario de p: pasa un punto de la pantalla al plano del mapa
function inv(sx,sy){const c=Math.cos(cam.b),s=Math.sin(cam.b);const rx=(sx-W/2)/cam.z,ry=(sy-H*0.55)/(cam.z*Math.max(.05,Math.cos(cam.p)));return [cam.x+rx*c+ry*s,cam.y-rx*s+ry*c]}

/* ---------- webgl ---------- */
const gl=glc.getContext('webgl2',{antialias:true,alpha:false,powerPreference:'high-performance'})||glc.getContext('webgl',{antialias:true,alpha:false,powerPreference:'high-performance'});const GL2=!!(gl&&window.WebGL2RenderingContext&&gl instanceof WebGL2RenderingContext);
let prog,buf={},tex=null,texReady=false,texD=null,texDReady=false;
if(!gl){document.getElementById('notice').hidden=false;document.getElementById('notice').textContent='Tu navegador no puede dibujar este mapa (WebGL desactivado).'}
else{
  const vs=`attribute vec3 p;attribute vec3 c;attribute vec4 w;uniform vec2 cam,res;uniform float z,b,tp,hk,us,ug,uz0;varying vec3 vc;varying vec4 vw;varying vec2 vg;
  void main(){float dx=p.x-cam.x,dy=p.y-cam.y;float co=cos(b),si=sin(b);float rx=dx*co-dy*si,ry=dx*si+dy*co,h=(us>0.5&&p.z>uz0?uz0+(p.z-uz0)*(1.0+ug):p.z)*hk;
    float sx=rx*z,sy=(ry*cos(tp)-h*sin(tp))*z;float d=ry*sin(tp)+h*cos(tp);
    gl_Position=vec4(sx/(res.x*.5),-(sy+res.y*.05)/(res.y*.5),-d/9000.0,1.0);vc=c;vw=w;vg=p.xy;}`;
  const fs=`precision mediump float;varying vec3 vc;varying vec4 vw;varying vec2 vg;uniform sampler2D t;uniform vec2 gsz;uniform float fh,dk,wr,uq,um;uniform vec3 uf,ut;
  void main(){vec3 vq=vc;if(uq>1.5)vq=mix(uf,vc,um);else if(uq>0.5){float k=dot(vc,vec3(1.0))/max(dot(ut,vec3(1.0)),0.01);vq=mix(uf*k,vc,um);}vec3 col=vq;
    if(vw.w<-2.5){col=dk>0.5?vec3(0.27,0.31,0.38):vec3(0.71,0.71,0.73);
      if(vq.g<0.5){float sx=fract(vg.x/6.0);if(abs(vg.y-vq.r*2000.0)>7.0&&sx<0.12)col=dk>0.5?vec3(0.55,0.60,0.66):vec3(0.96);}}
    else if(vw.w<-1.5){col=texture2D(t,vg/gsz).rgb;float st=step(fract((vg.x+vg.y)/7.0),0.42);vec3 gr=dk>0.5?vec3(0.30,0.75,0.48):vec3(0.16,0.62,0.34);col=mix(col,gr,0.08+0.17*st);}
    else if(vw.w<-0.5){col=texture2D(t,vg/gsz).rgb;}
    else if(vw.w>0.5){
      float L=vw.w,u=vw.x,f=vw.y/fh,fr=fract(f),k=vq.r/wr;
      if(f>vw.z-0.06){col=vq*1.05;}
      else if(fr<0.05){col=vq*0.91;}
      else if(u>2.5&&u<L-2.5&&fr>0.24&&fr<0.80){
        float m=fract((u-2.5)/6.5);
        if(fr<0.28){col=dk>0.5?vq*1.25:vec3(0.98,0.98,0.97)*k;}
        else if(m<0.08){col=dk>0.5?vq*0.85:vec3(0.80,0.81,0.82)*k;}
        else{
          float tt=(fr-0.28)/0.52;
          vec3 g=mix(vec3(0.30,0.39,0.49),vec3(0.67,0.77,0.86),tt);
          float s=fract((u*0.55+vw.y*0.9)/34.0);
          g+=vec3(0.08)*smoothstep(0.0,0.04,s)*(1.0-smoothstep(0.09,0.15,s));
          if(dk>0.5){float wi=floor((u-2.5)/6.5),fi=floor(f);float hh=fract(sin(wi*12.9898+fi*78.233+L*0.731)*43758.5453);
            g=hh>0.78?mix(vec3(0.86,0.76,0.56),vec3(0.80,0.66,0.46),tt)*0.85:mix(vec3(0.14,0.18,0.25),vec3(0.26,0.33,0.44),tt);}
          if(fr>0.74)g*=0.84;
          col=dk>0.5?g:g*k;
        }
      }
    }
    gl_FragColor=vec4(col,1.0);}`;
  const sh=(type,src)=>{const s=gl.createShader(type);gl.shaderSource(s,src);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))console.error(gl.getShaderInfoLog(s));return s};
  prog=gl.createProgram();gl.attachShader(prog,sh(gl.VERTEX_SHADER,vs));gl.attachShader(prog,sh(gl.FRAGMENT_SHADER,fs));gl.linkProgram(prog);gl.useProgram(prog);
  ['p','c','w'].forEach(a=>prog[a]=gl.getAttribLocation(prog,a));
  ['cam','res','z','b','tp','hk','t','gsz','fh','dk','wr','us','uq','ug','uz0','um','uf','ut'].forEach(u=>prog[u]=gl.getUniformLocation(prog,u));
  gl.enable(gl.DEPTH_TEST);gl.depthFunc(gl.LEQUAL);
  tex=gl.createTexture();const big=gl.getParameter(gl.MAX_TEXTURE_SIZE)>=4096;
  const loadTex=(src,hd)=>{const img=new Image();img.onload=function sube(){if(hd&&(ptr.size||INER||WZ||target)){setTimeout(sube,300);return}gl.bindTexture(gl.TEXTURE_2D,tex);gl.texImage2D(gl.TEXTURE_2D,0,gl.RGB,gl.RGB,gl.UNSIGNED_BYTE,img);
    const mip=GL2;if(mip)gl.generateMipmap(gl.TEXTURE_2D);
    gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,mip?gl.LINEAR_MIPMAP_LINEAR:gl.LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR);
    const an=gl.getExtension('EXT_texture_filter_anisotropic');if(an&&mip)gl.texParameterf(gl.TEXTURE_2D,an.TEXTURE_MAX_ANISOTROPY_EXT,Math.min(8,gl.getParameter(an.MAX_TEXTURE_MAX_ANISOTROPY_EXT)));
    gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);texReady=true;geoDirty=true;dirty=true;
    if(!hd&&big){const go=()=>{if(ptr.size||INER||WZ||target){setTimeout(go,500);return}loadTex(TABLET?UPIN.sueloMd:UPIN.sueloHd,true)};setTimeout(go,1800)}};img.src=src};
  // primero la versión liviana (aparece al tiro) y luego la nítida
  loadTex(UPIN.suelo,false);
}
/* geometría: triángulos (p,c,w) y líneas */
function Geo(){this.v=[];this.l=[]}
Geo.prototype.tri=function(a,b,c,col,w){for(const q of [a,b,c])this.v.push(q[0],q[1],q[2],col[0],col[1],col[2],w[0],w[1],w[2],w[3])};
Geo.prototype.quad=function(a,b,c,d,col,wa,wb,wc,wd){const W4=x=>x;this.v.push(...a,...col,...wa,...b,...col,...wb,...c,...col,...wc,...a,...col,...wa,...c,...col,...wc,...d,...col,...wd)};
Geo.prototype.line=function(a,b,col){this.l.push(...a,...col,0,0,0,0,...b,...col,0,0,0,0)};
const LIGHT=[-0.55,-0.83];

// dibuja un bloque con techo y paredes (edificios y salas en 2.5d)
function prism(g,pts,z0,h,top,wall,opt){opt=opt||{};let ps=pts.slice();if(area(ps)<0)ps.reverse();
  const T=hex(top),Wc=hex(wall),E=opt.edge||TH.edge;
  // techo: polígono normal, o rectángulos cuando el edificio tiene un patio interior (queda liso, sin costuras)
  const roofs=opt.hole?roofAround(ps,opt.hole):[ps];
  roofs.forEach(rp=>{const tri=triangulate(rp);for(let i=0;i<tri.length;i+=3)g.tri([rp[tri[i]][0],rp[tri[i]][1],z0+h],[rp[tri[i+1]][0],rp[tri[i+1]][1],z0+h],[rp[tri[i+2]][0],rp[tri[i+2]][1],z0+h],T,[0,0,0,0])});
  const ring=rg=>{for(let i=0;i<rg.length;i++){const a=rg[i],b=rg[(i+1)%rg.length];const L=Math.hypot(b[0]-a[0],b[1]-a[1]);if(L<0.01)continue;
    const nx=(b[1]-a[1])/L,ny=-(b[0]-a[0])/L;const k=0.80+0.17*Math.max(0,-(nx*LIGHT[0]+ny*LIGHT[1]))+0.03;
    const col=[Wc[0]*k,Wc[1]*k,Wc[2]*k],fl=opt.floors||0,wl=fl>0?L:0;
    g.quad([a[0],a[1],z0],[b[0],b[1],z0],[b[0],b[1],z0+h],[a[0],a[1],z0+h],col,[0,0,fl,wl],[L,0,fl,wl],[L,h,fl,wl],[0,h,fl,wl]);
    if(opt.lines!==false){g.line([a[0],a[1],z0+h],[b[0],b[1],z0+h],E);if(h>2)g.line([a[0],a[1],z0],[a[0],a[1],z0+h],E)}}};
  ring(ps);if(opt.hole){let hp=opt.hole.slice();if(area(hp)>0)hp.reverse();ring(hp)}
}
// techo alrededor de un patio rectangular: 4 rectángulos (arriba, abajo, izquierda, derecha)

// techo de un edificio con patio interior
function roofAround(ps,hole){const xs=ps.map(p=>p[0]),ys=ps.map(p=>p[1]),hx=hole.map(p=>p[0]),hy=hole.map(p=>p[1]);
  const X0=Math.min(...xs),X1=Math.max(...xs),Y0=Math.min(...ys),Y1=Math.max(...ys),a=Math.min(...hx),b=Math.max(...hx),c=Math.min(...hy),d=Math.max(...hy);
  const R=(x0,y0,x1,y1)=>[[x0,y0],[x1,y0],[x1,y1],[x0,y1]];return [R(X0,Y0,X1,c),R(X0,d,X1,Y1),R(X0,c,a,d),R(b,c,X1,d)]}

// dibuja un arbol simple de bajo costo
function treeGeo(g,x,y){const tr=hex('#7A6A55');const r=0.9;
  prism(g,[[x-r,y-r],[x+r,y-r],[x+r,y+r],[x-r,y+r]],0,11,'#7A6A55','#6B5C49',{lines:false});
  const cz=16,R=6.5,Hh=7,N=8,rings=[[-1,0.35],[-0.4,0.95],[0.35,0.9],[0.9,0.35],[1,0]];
  const base=hex(TH.tree);
  for(let j=0;j<rings.length-1;j++)for(let i=0;i<N;i++){const a0=i/N*6.283,a1=(i+1)/N*6.283;
    const v=(rr,ang)=>[x+Math.cos(ang)*R*rr[1],y+Math.sin(ang)*R*rr[1],cz+rr[0]*Hh];
    const p1=v(rings[j],a0),p2=v(rings[j],a1),p3=v(rings[j+1],a1),p4=v(rings[j+1],a0);
    const nx=Math.cos((a0+a1)/2),ny=Math.sin((a0+a1)/2),up=(rings[j][0]+rings[j+1][0])/2;
    const k=0.78+0.18*Math.max(0,-(nx*LIGHT[0]+ny*LIGHT[1]))+0.12*up;const col=[base[0]*k,base[1]*k,base[2]*k];
    g.tri(p1,p2,p3,col,[0,0,0,0]);g.tri(p1,p3,p4,col,[0,0,0,0])}}
const COLD={sala:'#7D889D',depto:'#8277A3',aula:'#8573B3',servicio:'#97737E',cafe:'#A6874F',gimnasio:'#3F80AD',casino:'#9E7E5B',patio:'#566174',rampa:'#727C8D',pasillo:'#7A6A68'};

// color de una sala segun su tipo
function roomCol(k){return DARK?(COLD[k]||'#5B6679'):(COL[k]||'#FFFFFF')}

// color final de una sala: escaleras y ascensores en gris
function rcol(r){const l=(r.label||'').toLowerCase();return (l.includes('escalera')||l.includes('ascensor'))?'#CFCECA':roomCol(r.kind)}
const LODZ=2.2;const GROUPS=GROUPS_DATA;let lastFar=null;

// true si la camara esta lejos (se muestran grupos en vez de salas sueltas)
function farNow(){return cam.z<LODZ}

/* ---------- modelos para distinguir espacios (escaleras, baños, comedores, auditorio) ---------- */

// oscurece o aclara un color (para las paredes)
function shade(c,k){return '#'+hex(c).map(v=>Math.round(Math.min(1,v*k)*255).toString(16).padStart(2,'0')).join('')}

// tipo especial de sala: escalera, rampa o baño
function rtype(r){const l=(r.label||'').toLowerCase();
  if(l.includes('escalera'))return 'esc';
  if(l==='rampa')return 'rampa';
  if(/^baño/.test(l))return 'bano';
  return null}
const MH={esc:14,bano:9,rampa:8};

// altura de cada bloque en 2.5d
function rh(r){return MH[rtype(r)]||RH[r.kind]||12}

// rectangulo que encierra un poligono
function bbox(p){const xs=p.map(q=>q[0]),ys=p.map(q=>q[1]);return [Math.min(...xs),Math.min(...ys),Math.max(...xs),Math.max(...ys)]}
function box(g,x0,y0,x1,y1,z0,h,col,ed){prism(g,[[x0,y0],[x1,y0],[x1,y1],[x0,y1]],z0,h,col,shade(col,0.78),ed?{edge:ed}:{lines:false})}

// dibujo especial de escaleras (escalones) y baños (mitad rosado, mitad celeste)
function roomModel(g,r,c,ed){
  if(r.kind==='restringido'){prism(g,r.pts,5,3,c,shade(c,0.85),{edge:ed});const [x0,y0,x1,y1]=bbox(r.pts),H=y1-y0,L=[0.62,0.61,0.58];
    for(let k=x0-H;k<x1;k+=6){let ax=k,ay=y1,bx=k+H,by=y0;if(ax<x0){ay-=x0-ax;ax=x0}if(bx>x1){by+=bx-x1;bx=x1}if(ay>by)g.line([ax,ay,8.2],[bx,by,8.2],L)}
    return true}
  if(r.kind==='estacionamiento'){prism(g,r.pts,5,1,c,shade(c,0.85),{lines:false});
    // líneas de estacionamientos
    const [x0,y0,x1,y1]=bbox(r.pts);const W=[0.97,0.97,0.98];
    if(x1-x0>14&&y1-y0>22)for(let y=y0+4;y+14<=y1-2;y+=36){g.line([x0+2,y+14,6.25],[x1-2,y+14,6.25],W);for(let x=x0+4;x<=x1-4;x+=8)g.line([x,y,6.25],[x,y+14,6.25],W)}
    return true}
  const t=rtype(r);if(!t)return false;
  const [x0,y0,x1,y1]=bbox(r.pts),w=x1-x0,h=y1-y0,Z=5;
  if(t==='esc'){ // escalones que suben a lo largo del lado más largo
    prism(g,r.pts,Z,1,shade(c,0.95),shade(c,0.8),{edge:ed});const N=Math.max(4,Math.min(9,Math.round(Math.max(w,h)/5)));
    const sc=DARK?'#8C93A3':'#C9C3BB';
    for(let i=0;i<N;i++){const zz=Z+1,hh=(i+1)*13/N,a=i/N,b=(i+1)/N;
      if(w>=h)box(g,x0+1+a*(w-2),y0+1,x0+1+b*(w-2),y1-1,zz,hh,i%2?sc:shade(sc,1.06),ed);
      else box(g,x0+1,y0+1+a*(h-2),x1-1,y0+1+b*(h-2),zz,hh,i%2?sc:shade(sc,1.06),ed)}
    return true}
  if(t==='rampa'){ // rampa peatonal con 4 tramos y descansos (como la foto de referencia), maciza y con barandas
    const wall=hex(sel===r?c:'#D8D4CD'),wall2=hex(shade(sel===r?c:'#D8D4CD',0.86)),floor_=hex('#7D7A75'),land_=hex('#8C8984'),rail=hex('#6B6863');
    const N=4,lane=(y1-y0)/N,land=Math.min(12,(x1-x0)*0.18),Ht=16,R=1.8;
    const solid=(xa,xb,ya,yb,za,zb,ftop)=>{ // bloque con techo inclinado de za (en xa) a zb (en xb)
      const A=[xa,ya,za],B=[xb,ya,zb],C=[xb,yb,zb],Dd=[xa,yb,za];g.tri(A,B,C,ftop,[0,0,0,0]);g.tri(A,C,Dd,ftop,[0,0,0,0]);
      g.tri([xa,ya,Z],[xb,ya,Z],B,wall,[0,0,0,0]);g.tri([xa,ya,Z],B,A,wall,[0,0,0,0]);
      g.tri([xa,yb,Z],[xb,yb,Z],C,wall2,[0,0,0,0]);g.tri([xa,yb,Z],C,Dd,wall2,[0,0,0,0]);
      g.tri([xa,ya,Z],[xa,yb,Z],Dd,wall2,[0,0,0,0]);g.tri([xa,ya,Z],Dd,A,wall2,[0,0,0,0]);
      g.tri([xb,ya,Z],[xb,yb,Z],C,wall,[0,0,0,0]);g.tri([xb,ya,Z],C,B,wall,[0,0,0,0])};
    const railing=(xa,xb,y,za,zb)=>{g.line([xa,y,za+R],[xb,y,zb+R],rail);g.line([xa,y,za+R*0.55],[xb,y,zb+R*0.55],rail);
      const n=Math.max(2,Math.round(Math.abs(xb-xa)/8));for(let i=0;i<=n;i++){const f=i/n,x=xa+(xb-xa)*f,z=za+(zb-za)*f;g.line([x,y,z],[x,y,z+R],rail)}};
    let z=Z+0.3;const w=lane*0.42,st=w*1.45,off=((y1-y0)-(st*(N-1)+w))/2;
    for(let i=0;i<N;i++){const yb=y1-off-i*st,ya=yb-w,za=z,zb=Z+0.3+Ht*(i+1)/N;
      const xa=i%2===0?x0+(i===0?0:land):x1-land,xbb=i%2===0?x1-land:x0+land;
      solid(Math.min(xa,xbb),Math.max(xa,xbb),ya,yb,i%2===0?za:zb,i%2===0?zb:za,floor_);
      railing(xa,xbb,ya,za,zb);railing(xa,xbb,yb,za,zb);
      if(i<N-1){const lx0=i%2===0?x1-land:x0,lx1=i%2===0?x1:x0+land;solid(lx0,lx1,yb-st-w,yb,zb,zb,land_);
        const ex=i%2===0?lx1:lx0;g.line([ex,yb-st-w,zb+R],[ex,yb,zb+R],rail)}
      z=zb}
    return true}
  if(t==='bano'){ // bloque bajo con una placa clara arriba y un inodoro estilizado al centro
    const mixto=r.building==='Edificio K';
    const pk=DARK?'#B57D93':'#F2B8CB',bl=DARK?'#6E9DC2':'#A8D2F0',mx=DARK?'#8E86C2':'#C9BEF0',H=3.2;
    const part=(ax0,ay0,ax1,ay1,col)=>{box(g,ax0,ay0,ax1,ay1,Z,H,col,ed);const i=Math.min(1.2,Math.min(ax1-ax0,ay1-ay0)*0.12);
      box(g,ax0+i,ay0+i,ax1-i,ay1-i,Z+H,0.25,shade(col,1.08),null)};
    if(sel===r)part(x0,y0,x1,y1,c);
    else if(mixto)part(x0,y0,x1,y1,mx);
    else{const [dir,first]=r.split||[w>=h?'x':'y','pk'];const A=first==='bl'?bl:pk,B=first==='bl'?pk:bl;
      if(dir==='x'){const m=(x0+x1)/2;part(x0,y0,m,y1,A);part(m,y0,x1,y1,B)}
      else{const m=(y0+y1)/2;part(x0,y0,x1,m,A);part(x0,m,x1,y1,B)}}
    const cx=(x0+x1)/2,cy=(y0+y1)/2,R=Math.max(1.5,Math.min(4.2,Math.min(w,h)*0.2)),zt=Z+H+0.25;
    const wh=DARK?'#E6EAF0':'#FFFFFF',rim=DARK?'#C3CAD6':'#E9EEF4',wat=DARK?'#7FA7CC':'#BFE0F7';
    const ell=(rx,ry,oy,n)=>{const p=[];for(let i=0;i<n;i++){const a=i/n*6.283;p.push([cx+Math.cos(a)*rx,cy+oy+Math.sin(a)*ry])}return p};
    prism(g,ell(R*0.55,R*0.6,R*0.35,16),zt,R*0.55,shade(wh,0.92),shade(wh,0.8),{lines:false});      // pie
    prism(g,ell(R*0.95,R*1.05,R*0.35,20),zt+R*0.55,R*0.45,wh,shade(wh,0.84),{lines:false});      // taza
    prism(g,ell(R*0.62,R*0.72,R*0.42,20),zt+R*1.0,0.12,wat,wat,{lines:false});                   // agua
    box(g,cx-R*0.85,cy-R*1.35,cx+R*0.85,cy-R*0.7,zt,R*1.75,wh,null);                              // estanque
    box(g,cx-R*0.95,cy-R*1.45,cx+R*0.95,cy-R*0.6,zt+R*1.75,R*0.2,rim,null);                       // tapa
    return true}
  if(t==='comida'){ // piso con mesas y sillas
    prism(g,r.pts,Z,2,c,shade(c,0.8),{edge:ed});
    const tb=DARK?'#B08A62':'#C8A27A',ch=DARK?'#6B5241':'#7A5A44',S=17,pad=5;
    for(let x=x0+pad+S/2;x<x1-pad;x+=S)for(let y=y0+pad+S/2;y<y1-pad;y+=S){if(!inPoly([x,y],r.pts))continue;
      box(g,x-3,y-2,x+3,y+2,Z+2,4.5,tb,null);
      box(g,x-4.6,y-1,x-3.6,y+1,Z+2,2.6,ch,null);box(g,x+3.6,y-1,x+4.6,y+1,Z+2,2.6,ch,null)}
    return true}
  if(t==='aula'){ // auditorio con filas de butacas que suben hacia atrás
    prism(g,r.pts,Z,1.5,c,shade(c,0.8),{edge:ed});const seat=DARK?'#7C5FA8':'#8E6CC4';const n=Math.floor((h-8)/4.5);
    for(let i=0;i<n;i++){const y=y0+6+i*4.5;box(g,x0+5,y,x1-5,y+2.6,Z+1.5,1.5+i*0.5,seat,null)}
    box(g,x0+5,y1-5,x1-5,y1-2,Z+1.5,2.5,shade(c,0.9),null);return true}
  return false}

// salas que se dibujan en el piso actual
function roomsVisible(){if(floor==='ext')return[];let rs=(FLOORS_DATA[floor]||[]).map((r,i)=>({r,i}));
  if(farNow()){const gs=GROUPS[floor]||[];rs=rs.filter(o=>!o.r.group);gs.forEach((g,i)=>rs.push({r:g,i:-1-i}))}return selB?rs.filter(o=>o.r.building===selB):rs}
let HIT=[];
let SELR={t:[],l:[]},SELP={t:[],l:[]},SELKEY=null,SELA=null,SELC={},PREVA=null,PREVOBJ=null,LASTOBJ=null,PREVC={};

// arma toda la geometria del mapa (suelo, edificios, salas, arboles)
function build(){
  const g=new Geo();SELR={t:[],l:[]};SELP={t:[],l:[]};const mk=(T)=>(fn)=>{const a=g.v.length/10,al=g.l.length/10;fn();T.t.push([a,g.v.length/10]);T.l.push([al,g.l.length/10])};const mark=mk(SELR),markP=mk(SELP);
  {const nk=sel?'r:'+(sel.label||'')+floor:(selB&&floor==='ext'?'b:'+selB:null);if(SELKEY&&nk!==SELKEY&&LASTOBJ&&!reduceMotion()){PREVOBJ=LASTOBJ;PREVA=performance.now()}LASTOBJ=sel||(selB&&floor==='ext'?selB:null)}const ext=floor==='ext';
  // suelo
  if(texReady){const w=S.w,h=S.h;const G=[0,0,0,-1];g.v.push(0,0,0,1,1,1,...G, w,0,0,1,1,1,...G, w,h,0,1,1,1,...G, 0,0,0,1,1,1,...G, w,h,0,1,1,1,...G, 0,h,0,1,1,1,...G)}
  (S.zones||[]).forEach(zn=>{let ps=zn.pts.slice();if(area(ps)<0)ps.reverse();const tri=triangulate(ps);
    const c=[Math.max(zn.mid||0,0)/2000,zn.mid>0?0:1,0],w=[0,0,0,zn.t==='parking'?-3:-2];
    for(let i=0;i<tri.length;i+=3)g.tri([...ps[tri[i]],0.3],[...ps[tri[i+1]],0.3],[...ps[tri[i+2]],0.3],c,w);
    if(zn.t==='segura')for(let i=0;i<ps.length;i++){const a=ps[i],b=ps[(i+1)%ps.length];g.line([a[0],a[1],0.4],[b[0],b[1],0.4],DARK?[0.35,0.75,0.5]:[0.17,0.55,0.3])}});
  S.buildings.forEach(b=>{const fl=BH[b.name]||b.floors||2,isSel=selB===b.name;
    if(b.bridge){if(ext)prism(g,b.pts,b.z0,b.h,TH.top,TH.wall,{floors:1});else if(floor==='2')prism(g,b.pts,0,5,TH.ftop,TH.fwall,{});return}
    if(ext&&isSel){mark(()=>prism(g,b.pts,0,fl*FH,DARK?'#C9A227':'#FFD45C',DARK?'#A8871F':'#F2C94C',{floors:b.name==='Casetas de seguridad'?0:fl,hole:b.hole,edge:[0.35,0.3,0.1]}));SELC={from:hex(TH.top),to:hex(DARK?'#C9A227':'#FFD45C'),lf:TH.edge,room:false}}
    else if(ext&&PREVA&&PREVOBJ===b.name){markP(()=>prism(g,b.pts,0,fl*FH,TH.top,TH.wall,{floors:b.name==='Casetas de seguridad'?0:fl,hole:b.hole}));PREVC={from:hex(DARK?'#C9A227':'#FFD45C'),to:hex(TH.top),lf:[0.35,0.3,0.1]}}
    else if(ext){const top=isSel?(DARK?'#C9A227':'#FFD45C'):TH.top,wall=isSel?(DARK?'#A8871F':'#F2C94C'):TH.wall;prism(g,b.pts,0,fl*FH,top,wall,{floors:b.name==='Casetas de seguridad'?0:fl,hole:b.hole,edge:isSel?[0.35,0.3,0.1]:undefined})}
    else{const dim=selB&&!isSel,fp=(b.fp&&b.fp[floor])||b.pts;if(!dim)prism(g,fp.map(q=>[q[0]+2.5,q[1]+3.5]),0,0.4,'#CBC7BE','#CBC7BE',{lines:false,hole:b.hole});prism(g,fp,0,5,dim?TH.dtop:TH.ftop,dim?TH.dwall:TH.fwall,{lines:!dim,hole:b.hole,edge:dim?undefined:[0.42,0.42,0.45]})}});
  roomsVisible().forEach(({r})=>{const c=sel===r?'#FFC72C':rcol(r);const h=RH[r.kind]||12;
    const wc=shade(c,0.8);const ed=sel===r?[0.1,0.1,0.1]:TH.redge;
    const draw=()=>{if(!roomModel(g,r,c,ed))prism(g,r.pts,5,h,c,wc,r.joined?{lines:false}:{edge:ed})};
    if(sel===r){mark(draw);SELC={from:hex(rcol(r)),to:hex('#FFC72C'),lf:TH.redge,room:true}}else if(PREVA&&PREVOBJ===r){markP(draw);PREVC={from:hex('#FFC72C'),to:hex(rcol(r)),lf:[0.1,0.1,0.1]}}else draw()});
  const key=sel?'r:'+(sel.label||'')+floor:(selB&&floor==='ext'?'b:'+selB:null);if(key&&key!==SELKEY&&!reduceMotion())SELA=performance.now();SELKEY=key;
  TREES.forEach(([x,y])=>treeGeo(g,x,y));
  if(!gl)return;
  for(const [k,arr] of [['tri',g.v],['line',g.l]]){if(!buf[k])buf[k]=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buf[k]);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(arr),gl.STATIC_DRAW);buf[k].n=arr.length/10}
  geoDirty=false;
}

// dibuja el mapa con la tarjeta grafica (webgl)
function drawGL(){
  if(!gl)return;if(geoDirty)build();
  gl.viewport(0,0,glc.width,glc.height);gl.clearColor(TH.clear[0],TH.clear[1],TH.clear[2],1);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);
  gl.uniform2f(prog.cam,cam.x,cam.y);gl.uniform2f(prog.res,W,H);gl.uniform1f(prog.z,cam.z);gl.uniform1f(prog.b,cam.b);gl.uniform1f(prog.tp,cam.p);gl.uniform1f(prog.hk,HK);gl.uniform1f(prog.us,0);gl.uniform1f(prog.ug,0);gl.uniform1f(prog.uz0,5.01);gl.uniform1f(prog.um,1);gl.uniform3f(prog.uf,1,1,1);gl.uniform3f(prog.ut,1,1,1);
  gl.uniform1f(prog.fh,FH);gl.uniform1f(prog.dk,DARK?1:0);gl.uniform1f(prog.wr,TH.wr);gl.uniform2f(prog.gsz,S.w,S.h);gl.activeTexture(gl.TEXTURE0);gl.bindTexture(gl.TEXTURE_2D,DARK&&texDReady?texD:tex);gl.uniform1i(prog.t,0);
  for(const k of ['tri','line']){const B=buf[k];if(!B||!B.n)continue;gl.bindBuffer(gl.ARRAY_BUFFER,B);
    gl.enableVertexAttribArray(prog.p);gl.vertexAttribPointer(prog.p,3,gl.FLOAT,false,40,0);
    gl.enableVertexAttribArray(prog.c);gl.vertexAttribPointer(prog.c,3,gl.FLOAT,false,40,12);
    gl.enableVertexAttribArray(prog.w);gl.vertexAttribPointer(prog.w,4,gl.FLOAT,false,40,24);
    if(k==='tri'){gl.enable(gl.POLYGON_OFFSET_FILL);gl.polygonOffset(1,1)}else gl.disable(gl.POLYGON_OFFSET_FILL);
    const kk=k==='tri'?'t':'l',mode=k==='tri'?gl.TRIANGLES:gl.LINES,R=[...(SELR[kk]||[]).map(r=>[r[0],r[1],0]),...(SELP[kk]||[]).map(r=>[r[0],r[1],1])].filter(r=>r[1]>r[0]).sort((a,b)=>a[0]-b[0]);
    gl.uniform1f(prog.us,0);gl.uniform1f(prog.uq,0);let pos=0;
    for(const [a,b2,tg] of R){if(a>pos)gl.drawArrays(mode,pos,a-pos);if(tg)prevUniforms(k);else selUniforms(k);gl.drawArrays(mode,a,b2-a);gl.uniform1f(prog.us,0);gl.uniform1f(prog.uq,0);pos=b2}
    if(B.n>pos)gl.drawArrays(mode,pos,B.n-pos)}
}

/* ---------- capa 2d: nombres, accesos y monito ---------- */
function prevUniforms(k){let t=PREVA?(performance.now()-PREVA)/300:1;if(t>=1){t=1;PREVA=null}const e=1-Math.pow(1-t,3);
  gl.uniform1f(prog.us,0);gl.uniform1f(prog.uq,k==='tri'?1:2);gl.uniform1f(prog.um,e);gl.uniform1f(prog.ug,0);
  const f=k==='tri'?PREVC.from:PREVC.lf;gl.uniform3f(prog.uf,f[0],f[1],f[2]);const to=PREVC.to;gl.uniform3f(prog.ut,to[0],to[1],to[2])}
function selProgress(){if(!SELA)return 1;const t=(performance.now()-SELA)/380;if(t>=1){SELA=null;return 1}return t}
function selUniforms(k){const t=selProgress(),e=1-Math.pow(1-t,3);
  gl.uniform1f(prog.us,k==='tri'?1:2);gl.uniform1f(prog.uq,k==='tri'?1:2);gl.uniform1f(prog.um,e);gl.uniform1f(prog.uz0,5.01);
  gl.uniform1f(prog.ug,SELC.room?0.16*Math.sin(Math.PI*Math.min(1,t*1.15))*(1-t*0.4):0);
  const f=k==='tri'?SELC.from:SELC.lf;gl.uniform3f(prog.uf,f[0],f[1],f[2]);const to=SELC.to;gl.uniform3f(prog.ut,to[0],to[1],to[2])}

// iconos de escalera y ascensor sobre el mapa
function mapIcon(x,y,s,kind,on){if(kind==='both'){stairIcon(x-s/2-1.5,y,s,on);liftIcon(x+s/2+1.5,y,s,on)}else if(kind==='esc')stairIcon(x,y,s,on);else liftIcon(x,y,s,on)}
function liftIcon(x,y,s,on){ctx.save();ctx.fillStyle=on?'#1D1D1F':'#2F6FB5';ctx.beginPath();ctx.roundRect(x-s/2,y-s/2,s,s,s*0.28);ctx.fill();ctx.fillStyle='#fff';const u=s/24;
  ctx.beginPath();ctx.moveTo(x-4*u,y-2*u);ctx.lineTo(x,y-7*u);ctx.lineTo(x+4*u,y-2*u);ctx.closePath();ctx.fill();
  ctx.beginPath();ctx.moveTo(x-4*u,y+2*u);ctx.lineTo(x,y+7*u);ctx.lineTo(x+4*u,y+2*u);ctx.closePath();ctx.fill();ctx.restore()}
function stairIcon(x,y,s,on){ctx.save();ctx.fillStyle=on?'#1D1D1F':'rgba(60,60,67,.88)';ctx.beginPath();ctx.roundRect(x-s/2,y-s/2,s,s,s*0.28);ctx.fill();
  ctx.strokeStyle='#fff';ctx.lineWidth=Math.max(1.6,s*0.09);ctx.lineCap='round';ctx.lineJoin='round';const u=s/24;ctx.beginPath();
  ctx.moveTo(x-7*u,y+6*u);ctx.lineTo(x-3*u,y+6*u);ctx.lineTo(x-3*u,y+2*u);ctx.lineTo(x+1*u,y+2*u);ctx.lineTo(x+1*u,y-2*u);ctx.lineTo(x+5*u,y-2*u);ctx.lineTo(x+5*u,y-6*u);ctx.lineTo(x+7*u,y-6*u);ctx.stroke();ctx.restore()}
const LSPR=new Map();

// guarda los nombres ya dibujados para no redibujarlos cada vez (rendimiento)
function labSprite(t,size,weight,color){const sz=Math.max(6,Math.round(size*2)/2),key=t+'|'+sz+'|'+weight+'|'+color;let sp=LSPR.get(key);if(sp)return sp;
  if(LSPR.size>1800)LSPR.clear();const c=document.createElement('canvas'),o=c.getContext('2d'),font=`${weight} ${sz}px -apple-system,BlinkMacSystemFont,Inter,sans-serif`;
  o.font=font;const tw=o.measureText(t).width,cw=Math.ceil(tw+10),ch=Math.ceil(sz*1.6+6),r=Math.min(2,devicePixelRatio||1);
  c.width=cw*r;c.height=ch*r;o.scale(r,r);o.font=font;o.textAlign='center';o.textBaseline='middle';o.lineJoin='round';
  o.lineWidth=4;o.strokeStyle='rgba(255,255,255,.95)';o.strokeText(t,cw/2,ch/2);o.fillStyle=color;o.fillText(t,cw/2,ch/2);
  sp={c,cw,ch,tw,sz};LSPR.set(key,sp);return sp}

// capa de arriba: nombres de salas y edificios, accesos, pines y tu ubicacion
function drawOverlay(){
  ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,W,H);try{selOutline()}catch(e){}ctx.globalAlpha=LA;ctx.textAlign='center';ctx.textBaseline='middle';ctx.lineJoin='round';
  const boxes=[];const fits=(t,x,y,size,weight)=>{const sp=labSprite(t,size,weight,'#1D1D1F'),w=sp.tw*size/sp.sz+6,h=size+4,X=x-w/2,Y=y-h/2;for(const b of boxes)if(X<b[0]+b[2]&&X+w>b[0]&&Y<b[1]+b[3]&&Y+h>b[1])return false;return true};const free=(x,y,w,h)=>{for(const b of boxes)if(x<b[0]+b[2]&&x+w>b[0]&&y<b[1]+b[3]&&y+h>b[1])return false;boxes.push([x,y,w,h]);return true};
  const lab=(t,x,y,size,weight,color,force)=>{const sp=labSprite(t,size,weight,color),k=size/sp.sz,w=sp.tw*k+6,h=size+4;
    if(x<-w||x>W+w||y<-h||y>H+h)return false;if(!free(x-w/2,y-h/2,w,h)&&!force)return false;ctx.drawImage(sp.c,x-sp.cw*k/2,y-sp.ch*k/2,sp.cw*k,sp.ch*k)};
  const zs=Math.max(.75,Math.min(1.6,cam.z));
  // accesos
  S.acc.forEach(([t,x,y])=>{const p=P(x,y,0);ctx.fillStyle='#1D1D1F';ctx.beginPath();ctx.arc(p[0],p[1],11,0,7);ctx.fill();ctx.fillStyle='#FFC72C';
    ctx.beginPath();ctx.moveTo(p[0]-5,p[1]-3);ctx.lineTo(p[0]+5,p[1]-3);ctx.lineTo(p[0],p[1]+5);ctx.closePath();ctx.fill();lab(t,p[0],p[1]-22,11.5,600,'#1D1D1F',true)});
  // puntos de interés (cargadores, seguridad, estacionamiento)
  if(floor==='ext')(S.poi||[]).forEach(([t,x,y,k])=>{const p=P(x,y,0);const col={carga:'#2F9E44',seguridad:'#1F3A5F',parking:'#1971C2'}[k];
    ctx.fillStyle=col;ctx.strokeStyle='#fff';ctx.lineWidth=2;
    if(k==='parking'){ctx.beginPath();ctx.roundRect(p[0]-11,p[1]-11,22,22,5);ctx.fill();ctx.stroke();ctx.fillStyle='#fff';ctx.font='700 14px -apple-system,Inter,sans-serif';ctx.fillText('P',p[0],p[1]+1)}
    else{ctx.beginPath();ctx.arc(p[0],p[1],11,0,7);ctx.fill();ctx.stroke();ctx.strokeStyle='#fff';ctx.lineWidth=1.8;ctx.beginPath();
      if(k==='carga'){ctx.moveTo(p[0]+1,p[1]-6);ctx.lineTo(p[0]-4,p[1]+1);ctx.lineTo(p[0]+1,p[1]+1);ctx.lineTo(p[0]-1,p[1]+6);ctx.lineTo(p[0]+4,p[1]-1);ctx.lineTo(p[0]-1,p[1]-1);ctx.closePath()}
      else{ctx.moveTo(p[0],p[1]-6);ctx.lineTo(p[0]+5,p[1]-4);ctx.quadraticCurveTo(p[0]+5,p[1]+3,p[0],p[1]+6);ctx.quadraticCurveTo(p[0]-5,p[1]+3,p[0]-5,p[1]-4);ctx.closePath()}ctx.stroke()}
    lab(t,p[0],p[1]-20,11.5,600,'#1D1D1F')});
  // zonas de seguridad: letra pintada en el suelo (a, b, c)
  (S.zones||[]).forEach(zn=>{if(!zn.letra)return;const k=zn.small?0.62:1,o=P(zn.lx,zn.ly,0.5),ex=P(zn.lx+k,zn.ly,0.5),ey=P(zn.lx,zn.ly+k,0.5);
    ctx.setTransform(dpr*(ex[0]-o[0]),dpr*(ex[1]-o[1]),dpr*(ey[0]-o[0]),dpr*(ey[1]-o[1]),dpr*o[0],dpr*o[1]);
    ctx.globalAlpha=0.42;ctx.fillStyle=DARK?'#2F9E5A':'#1E8E4A';ctx.beginPath();ctx.roundRect(-13,-13,26,26,4);ctx.fill();
    ctx.globalAlpha=0.7;ctx.strokeStyle='#fff';ctx.lineWidth=1.6;ctx.beginPath();ctx.arc(0,0,9.5,0,7);ctx.stroke();
    ctx.fillStyle='#fff';ctx.font='700 13px -apple-system,Inter,sans-serif';ctx.fillText(zn.letra,0,1);ctx.globalAlpha=1;ctx.setTransform(dpr,0,0,dpr,0,0)});
  if(floor==='ext')(S.zones||[]).forEach(zn=>{if(zn.t!=='parking'||!zn.n)return;const c=centroid(zn.pts),p=P(c[0],c[1],0);lab(zn.n,p[0],p[1],11.5*zs,700,DARK?'#B8BEC8':'#55555C')});
  HIT=[];
  if(floor==='ext'){
    S.labels.forEach(([t,x,y])=>{const p=P(x,y,(BH[t]||2)*FH+4);lab(t,p[0],p[1],15*zs,700,'#1D1D1F',t===selB)});
  }else{
    const rs=roomsVisible().map(o=>{const top=o.r.pts.map(q=>P(q[0],q[1],5+rh(o.r)));const c=o.r.at?P(o.r.at[0],o.r.at[1],5+rh(o.r)):centroid(top);return {r:o.r,top,c,d:P(...centroid(o.r.pts),5)[2]}});
    rs.sort((a,b)=>a.d-b.d);HIT=rs;
    // salas grandes primero
    [...rs].sort((a,b)=>((b.r._lv?1:0)-(a.r._lv?1:0))||(Math.abs(area(b.r.pts))-Math.abs(area(a.r.pts)))||(a.r.label<b.r.label?-1:1)).forEach(o=>{if(!o.r.label||o.r.kind==='pasillo'||o.r.nolab)return;
      {const L=o.r.label.toLowerCase(),es=L.includes('escalera'),as=L.includes('ascensor');if(es||as){const sz=Math.max(15,Math.min(24,18*zs));if(cam.z<0.9)return;const kind=es&&as?'both':es?'esc':'asc';const ww=kind==='both'?sz*2+3:sz;if(!free(o.c[0]-ww/2,o.c[1]-sz/2,ww,sz)&&sel!==o.r)return;mapIcon(o.c[0],o.c[1],sz,kind,sel===o.r);o.r._lv=true;return}}
      const [bx0,by0,bx1,by1]=bbox(o.r.pts);const w=Math.max(o.r.lbw||(bx1-bx0),(o.r.lbh||(by1-by0))*0.6)*cam.z;
      const fs=Math.min(13*zs,w*0.85/Math.max(3,o.r.label.length)*1.7)*(o.r.ls||1);const need=o.r._lv?7:8.5;
      if(o.r.label.includes(' ')){ // nombres largos: en dos líneas si así se leen mejor
        const wd=o.r.label.split(' ');let best=null;for(let i=1;i<wd.length;i++){const l1=wd.slice(0,i).join(' '),l2=wd.slice(i).join(' ');const m=Math.max(l1.length,l2.length);if(!best||m<best[2])best=[l1,l2,m]}
        const f2=Math.min(13*zs,w*0.85/Math.max(3,best[2])*1.7)*(o.r.ls||1);if(f2>=need&&(fs<need||f2>fs*1.3)){const fz=Math.max(f2,8);
          const ok=sel===o.r||(fits(best[0],o.c[0],o.c[1]-fz*0.6,fz,600)&&fits(best[1],o.c[0],o.c[1]+fz*0.6,fz,600));if(ok){lab(best[0],o.c[0],o.c[1]-fz*0.6,fz,600,'#1D1D1F',true);lab(best[1],o.c[0],o.c[1]+fz*0.6,fz,600,'#1D1D1F',true)}o.r._lv=ok;return}}
      if(fs<need){o.r._lv=false;return}o.r._lv=lab(o.r.label,o.c[0],o.c[1],Math.max(fs,8),600,'#1D1D1F',sel===o.r)!==false});
    if(!selB&&cam.z<1.1)S.labels.forEach(([t,x,y])=>{const p=P(x,y,40);lab(t,p[0],p[1],13*zs,700,'rgba(29,29,31,.55)')});
  }
  S.ground.forEach(([t,x,y])=>{if(t==='Auditorio'&&floor!=='ext'&&floor!=='1')return;const p=P(x,y,0);lab(t,p[0],p[1],12*zs,600,'#3B4A1E')});
  if(me&&me.acc){const p=P(me.x,me.y,0);const r=me.acc/GEO.s*cam.z;const fl=Math.max(.4,Math.cos(cam.p));
    ctx.fillStyle='rgba(25,113,194,.12)';ctx.strokeStyle='rgba(25,113,194,.45)';ctx.lineWidth=1.5;ctx.beginPath();ctx.ellipse(p[0],p[1],r,r*fl,0,0,7);ctx.fill();ctx.stroke()}
  if(me){const p=P(me.x,me.y,0),t=P(me.x,me.y,22);const pulse=(Date.now()%1600)/1600;const fl=Math.max(.4,Math.cos(cam.p));
    ctx.fillStyle=`rgba(255,199,44,${.35*(1-pulse)})`;ctx.beginPath();ctx.ellipse(p[0],p[1],10+26*pulse,(10+26*pulse)*fl,0,0,7);ctx.fill();
    ctx.fillStyle='rgba(0,0,0,.2)';ctx.beginPath();ctx.ellipse(p[0],p[1],8,8*fl,0,0,7);ctx.fill();
    ctx.strokeStyle='#2B2100';ctx.lineWidth=2;ctx.beginPath();ctx.moveTo(p[0],p[1]);ctx.lineTo(t[0],t[1]+8);ctx.stroke();
    ctx.fillStyle='#FFC72C';ctx.beginPath();ctx.arc(t[0],t[1],10,0,7);ctx.fill();ctx.stroke();
    ctx.fillStyle='#2B2100';ctx.beginPath();ctx.arc(t[0]-3.5,t[1]-2,1.6,0,7);ctx.arc(t[0]+3.5,t[1]-2,1.6,0,7);ctx.fill();
    ctx.beginPath();ctx.arc(t[0],t[1]+1,4,0.15*Math.PI,0.85*Math.PI);ctx.stroke();dirty=true}
  document.querySelector('#compass svg').style.transform=`rotate(${cam.b}rad)`;
}
// la imagen 3d se dibuja con un tope de píxeles y baja la resolución sola si el equipo va lento
var GQ=1,INTQ=1,lastTouch=0;const TABLET=matchMedia('(pointer:coarse)').matches;function glScale(){return Math.min(dpr,Math.sqrt((TABLET?2.8e6:4.2e6)/Math.max(1,W*H)))*GQ*INTQ}

// ajusta la resolucion del mapa al tamaño de la pantalla
function resizeGL(){const g=glScale(),w=Math.round(W*g),h=Math.round(H*g);if(glc.width!==w||glc.height!==h){glc.width=w;glc.height=h}dirty=true}
function resize(){dpr=Math.min(TABLET&&cv.clientWidth*cv.clientHeight>500000?1.6:2,devicePixelRatio||1);W=cv.clientWidth;H=cv.clientHeight;cv.width=W*dpr;cv.height=H*dpr;const g=glScale();glc.width=Math.round(W*g);glc.height=Math.round(H*g);dirty=true}
new ResizeObserver(resize).observe(cv);resize();
const ZMIN=.25,ZMAX=6,VEL={x:0,y:0,z:0,b:0,p:0};let INER=null,WZ=null,lastT=performance.now();

// movimiento suave tipo resorte para la camara
function damp(cur,tgt,k,st,dt){const om=2/st,x=om*dt,ex=1/(1+x+0.48*x*x+0.235*x*x*x);const ch=cur-tgt,tmp=(VEL[k]+om*ch)*dt;VEL[k]=(VEL[k]-om*tmp)*ex;return tgt+(ch+tmp)*ex}

// acerca o aleja la camara manteniendo fijo el punto bajo el dedo
function zoomAround(nz,sx,sy){const a=inv(sx,sy);cam.z=nz;const b=inv(sx,sy);cam.x+=a[0]-b[0];cam.y+=a[1]-b[1]}
var FT={ema:16,slow:0,fast:0,was:false};
(function loop(now){now=now||performance.now();const rawdt=now-lastT;const dt=Math.min(0.05,Math.max(0.001,rawdt/1000));lastT=now;
  if(FT.was&&rawdt<200){FT.ema=FT.ema*0.9+rawdt*0.1;if(FT.ema>26){if(++FT.slow>40&&GQ>0.8){GQ=Math.max(0.8,GQ-0.1);FT.slow=0;FT.ema=16;resize()}}else FT.slow=0;
    if(FT.ema<13){if(++FT.fast>240&&GQ<1){GQ=Math.min(1,GQ+0.1);FT.fast=0;resize()}}else FT.fast=0}FT.was=dirty;
  if(FA)floorStep(now);if(SELA||PREVA)dirty=true;const fn=farNow();if(fn!==lastFar){lastFar=fn;if(floor!=='ext')geoDirty=true;dirty=true}
  if(target){let done=true;const st=target._st||0.26;
    for(const k in target){if(k[0]==='_')continue;const tg=target[k];
      if(k==='z'){const lz=damp(Math.log(cam.z),Math.log(tg),'z',st,dt);cam.z=Math.exp(lz)}else cam[k]=damp(cam[k],tg,k,st,dt);
      const d=k==='z'?Math.log(cam.z/tg):cam[k]-tg;if(Math.abs(d)>(k==='x'||k==='y'?0.01:1e-4)||Math.abs(VEL[k])>(k==='x'||k==='y'?0.5:1e-3))done=false}
    if(done){for(const k in target)if(k[0]!=='_'){cam[k]=target[k];VEL[k]=0}target=null}dirty=true}
  else if(INER){const f=Math.exp(-dt*4.2),fz=Math.exp(-dt*7);INER.x*=f;INER.y*=f;INER.b*=fz;INER.z*=fz;
    cam.x+=INER.x*dt;cam.y+=INER.y*dt;cam.b+=INER.b*dt;if(INER.z){zoomAround(Math.max(ZMIN,Math.min(ZMAX,cam.z*Math.exp(INER.z*dt))),INER.sx,INER.sy)}
    if(Math.hypot(INER.x,INER.y)<3&&Math.abs(INER.b)<0.01&&Math.abs(INER.z)<0.01)INER=null;dirty=true}
  if(WZ&&WZ.d){const t=Math.min(1,(now-WZ.t0)/WZ.d),e=t<.5?4*t*t*t:1-Math.pow(-2*t+2,3)/2;zoomAround(Math.exp(Math.log(WZ.z0)+(Math.log(WZ.z)-Math.log(WZ.z0))*e),WZ.sx,WZ.sy);if(t>=1)WZ=null;dirty=true}
  else if(WZ){const nz=Math.exp(Math.log(cam.z)+(Math.log(WZ.z)-Math.log(cam.z))*(1-Math.exp(-dt*10)));zoomAround(nz,WZ.sx,WZ.sy);if(Math.abs(Math.log(cam.z/WZ.z))<1e-3){zoomAround(WZ.z,WZ.sx,WZ.sy);WZ=null}dirty=true}
  try{if(INTQ<1&&!ptr.size&&!INER&&now-lastTouch>160){INTQ=1;resizeGL()}}catch(e){}
  try{if(!ptr.size&&!WZ&&(!target||!('x' in target))&&outB()){if(INER){INER.x=0;INER.y=0}animTo(clampB(),0.3)}}catch(e){}
  if(dirty){dirty=false;drawGL();drawOverlay()}requestAnimationFrame(loop)})();

// zoom animado
function zoomTo(z,sx,sy,d){z=Math.max(ZMIN,Math.min(ZMAX,z));if(reduceMotion()){zoomAround(z,sx,sy);dirty=true;return}target=null;INER=null;WZ={z0:cam.z,z,sx,sy,t0:performance.now(),d:d||520};dirty=true}

// mueve la camara de forma animada a otra posicion
function animTo(o,st){if(reduceMotion()){Object.assign(cam,o);dirty=true;return}INER=null;WZ=null;
  if('b' in o){let d=o.b-cam.b;d=Math.atan2(Math.sin(d),Math.cos(d));o=Object.assign({},o,{b:cam.b+d})}
  if('z' in o)o.z=Math.max(ZMIN,Math.min(ZMAX,o.z));
  // viajes largos: un poco más pausados, como en apple maps
  if(('x' in o)&&!st){const dd=Math.hypot(o.x-cam.x,o.y-cam.y)*cam.z/Math.max(W,H);st=dd>1.2?0.6:dd>0.5?0.5:0.4}
  target=Object.assign({},target||{},o,{_st:st||0.4})}

// vuelve a armar el mapa cuando cambia el piso o la seleccion
function rebuild(){geoDirty=true;dirty=true}

/* ---------- gestos ---------- */
const ptr=new Map();let moved=0,g0=null;
const BX=[150,1450],BY=[90,1430];
const outB=()=>cam.x<BX[0]||cam.x>BX[1]||cam.y<BY[0]||cam.y>BY[1];
const clampB=()=>({x:Math.max(BX[0],Math.min(BX[1],cam.x)),y:Math.max(BY[0],Math.min(BY[1],cam.y))});
const SAMP=[];function samp(){const t=performance.now();SAMP.push({t,x:cam.x,y:cam.y,z:Math.log(cam.z),b:cam.b});while(SAMP.length&&t-SAMP[0].t>120)SAMP.shift()}
const soft=z=>z>ZMAX?ZMAX*Math.pow(z/ZMAX,0.3):z<ZMIN?ZMIN*Math.pow(z/ZMIN,0.3):z;let zRaw=1;
cv.addEventListener('pointerdown',e=>{cv.setPointerCapture(e.pointerId);lastTouch=performance.now();target=null;INER=null;WZ=null;for(const k in VEL)VEL[k]=0;SAMP.length=0;zRaw=cam.z;ptr.set(e.pointerId,{x:e.clientX,y:e.clientY,b:e.button,sh:e.shiftKey});moved=0;target=null;cv.classList.add('drag');if(ptr.size===2)g0=gest()});
cv.addEventListener('pointermove',e=>{if(!ptr.has(e.pointerId))return;lastTouch=performance.now();const p=ptr.get(e.pointerId);const dx=e.clientX-p.x,dy=e.clientY-p.y;
  if(ptr.size===1){moved+=Math.abs(dx)+Math.abs(dy);
    if(p.b===2||p.sh){cam.b+=dx*0.006;cam.p=Math.max(0,Math.min(1.15,cam.p-dy*0.005))}
    else{const a=inv(W/2,H*0.55),b=inv(W/2-dx,H*0.55-dy);let mx=b[0]-a[0],my=b[1]-a[1];
      const rb=o=>Math.max(0,1-o/120)**2;if(cam.x<BX[0]&&mx<0)mx*=rb(BX[0]-cam.x);if(cam.x>BX[1]&&mx>0)mx*=rb(cam.x-BX[1]);if(cam.y<BY[0]&&my<0)my*=rb(BY[0]-cam.y);if(cam.y>BY[1]&&my>0)my*=rb(cam.y-BY[1]);cam.x+=mx;cam.y+=my}
    p.x=e.clientX;p.y=e.clientY;samp();dirty=true}
  else{p.x=e.clientX;p.y=e.clientY;const g=gest();if(g0){const mx=(g.cx+g0.cx)/2,my2=(g.cy+g0.cy)/2;zRaw*=g.d/g0.d;const r0=cv.getBoundingClientRect();zoomAround(soft(zRaw),mx-r0.left,my2-r0.top);{const A=inv(g0.cx-r0.left,g0.cy-r0.top),B=inv(g.cx-r0.left,g.cy-r0.top);cam.x+=A[0]-B[0];cam.y+=A[1]-B[1]}cam.b+=g.a-g0.a;cam.p=Math.max(0,Math.min(1.15,cam.p-(g.my-g0.my)*0.004));g0=g;moved+=99;samp();dirty=true}}});

// lee dos dedos: distancia y angulo para zoom y giro
function gest(){const [a,b]=[...ptr.values()];return{d:Math.hypot(a.x-b.x,a.y-b.y)||1,a:Math.atan2(b.y-a.y,b.x-a.x),my:(a.y+b.y)/2,cx:(a.x+b.x)/2,cy:(a.y+b.y)/2}}
const up=e=>{const p=ptr.get(e.pointerId);const wasPinch=ptr.size===2;ptr.delete(e.pointerId);g0=ptr.size===2?gest():null;zRaw=cam.z;
  if(!ptr.size){cv.classList.remove('drag');release(wasPinch,e)}if(p&&moved<6&&e.type==='pointerup')tap(e)};

// al soltar el dedo: sigue moviendose un poco (inercia)
function release(pinch,e){const t=performance.now();while(SAMP.length&&t-SAMP[0].t>100)SAMP.shift();
  if(cam.z>ZMAX||cam.z<ZMIN){const r=cv.getBoundingClientRect();WZ={z:Math.max(ZMIN,Math.min(ZMAX,cam.z)),sx:e.clientX-r.left,sy:e.clientY-r.top};return}
  if(reduceMotion()||SAMP.length<2||moved<6)return;const a=SAMP[0],dt=(t-a.t)/1000;if(dt<0.016||t-SAMP[SAMP.length-1].t>60)return;
  const vx=(cam.x-a.x)/dt,vy=(cam.y-a.y)/dt,vb=pinch?(cam.b-a.b)/dt:0,vz=pinch?(Math.log(cam.z)-a.z)/dt:0;
  const sp=Math.hypot(vx,vy)*cam.z;const r=cv.getBoundingClientRect();
  INER={x:sp>120?vx:0,y:sp>120?vy:0,b:Math.abs(vb)>0.4?vb*0.6:0,z:Math.abs(vz)>0.6?vz*0.5:0,sx:W/2,sy:H/2};if(sp>3000*1){const k=3000/sp;INER.x*=k;INER.y*=k}}
// doble toque: acerca hacia ese punto
let lastTap=null;
cv.addEventListener('pointerup',up);cv.addEventListener('pointercancel',up);cv.addEventListener('contextmenu',e=>e.preventDefault());
cv.addEventListener('wheel',e=>{e.preventDefault();const r=cv.getBoundingClientRect();const sx=e.clientX-r.left,sy=e.clientY-r.top;target=null;INER=null;
  const k=e.ctrlKey?0.01:0.0022;const base=WZ&&!WZ.d?WZ.z:cam.z;const nz=Math.max(ZMIN,Math.min(ZMAX,base*Math.exp(-e.deltaY*k)));
  if(reduceMotion()){zoomAround(nz,sx,sy);dirty=true}else WZ={z:nz,sx,sy,d:0};dirty=true},{passive:false});

// edificio que esta bajo el punto tocado
function buildingAt(pt){let best=null,bd=-1e9;
  S.buildings.forEach(b=>{if(b.bridge)return;const h=floor==='ext'?(BH[b.name]||2)*FH:5;const top=b.pts.map(q=>P(q[0],q[1],h));if(inPoly(pt,top)){const d=P(...centroid(b.pts),h)[2];if(d>bd){bd=d;best=b}}});return best}
// elegir la sala tocada: la más chica que contenga el punto; fondos, patios y pasillos solo si no hay otra
const BGK={patio:1,pasillo:1,estacionamiento:1,rampa:1};

// sala tocada: la mas chica bajo el dedo; pasillos y patios solo si no hay otra
function pickRoom(pt){let bg=null,bs=1e18;for(let i=HIT.length-1;i>=0;i--){const o=HIT[i];if(!inPoly(pt,o.top))continue;
  if(BGK[o.r.kind]||(!o.r.label&&o.r.kind==='restringido')){const a=Math.abs(area(o.r.pts));if(a<bs){bs=a;bg=o.r}continue}return o.r}return bg}

// que pasa al tocar el mapa: sala, edificio o lugar exterior (doble toque = zoom)
function tap(e){const r=cv.getBoundingClientRect();const pt=[e.clientX-r.left,e.clientY-r.top];const now=performance.now();
  if(lastTap&&now-lastTap.t<300&&Math.hypot(pt[0]-lastTap.x,pt[1]-lastTap.y)<30){lastTap=null;zoomTo(cam.z*2,pt[0],pt[1],560);return}lastTap={t:now,x:pt[0],y:pt[1]};
  {const h=pickRoom(pt);if(h){openRoom(h);return}}
  const b=buildingAt(pt);if(b){if(floor==='ext'||b.name!==selB)selectBuilding(b.name);return}
  {const pl=placeAt(pt);if(pl){openRoom(pl);return}}}
document.getElementById('zin').onclick=()=>zoomTo((WZ?WZ.z:cam.z)*1.6,W/2,H*0.55,420);
document.getElementById('zout').onclick=()=>zoomTo((WZ?WZ.z:cam.z)/1.6,W/2,H*0.55,420);
document.getElementById('rl').onclick=()=>animTo({b:cam.b-Math.PI/8});
document.getElementById('rr').onclick=()=>animTo({b:cam.b+Math.PI/8});
document.getElementById('compass').onclick=()=>animTo({b:0});
const m25=document.getElementById('m25'),m2d=document.getElementById('m2d');
m25.onclick=()=>{animTo({p:0.95},0.3);m25.setAttribute('aria-pressed',true);m2d.setAttribute('aria-pressed',false)};
m2d.onclick=()=>{animTo({p:0},0.3);m2d.setAttribute('aria-pressed',true);m25.setAttribute('aria-pressed',false)};

/* ---------- edificio seleccionado ---------- */
const chip=document.getElementById('chip');

// elegir un edificio: lo marca y muestra su tarjeta
function selectBuilding(name){selB=name;sel=null;closeSheet(true);
  chip.hidden=!name;if(name){document.getElementById('chipName').textContent=name;document.getElementById('chipIn').hidden=floor!=='ext';
    const pts=S.buildings.filter(b=>b.name===name).flatMap(b=>b.pts);const xs=pts.map(p=>p[0]),ys=pts.map(p=>p[1]);
    const md=Math.max(Math.max(...xs)-Math.min(...xs),Math.max(...ys)-Math.min(...ys));animTo({x:(Math.min(...xs)+Math.max(...xs))/2,y:(Math.min(...ys)+Math.max(...ys))/2,z:Math.max(0.6,Math.min(2.4,0.7*Math.min(W,H)/md))})}
  paintFloors();updNotice();rebuild()}
document.getElementById('chipX').onclick=()=>selectBuilding(null);
document.getElementById('chipIn').onclick=()=>setFloor('1');

/* ---------- pisos ---------- */
const FLOORS=['6','5','4','3','2','1','-1','-2','ext'];
const nav=document.getElementById('floors');
FLOORS.forEach(f=>{const b=document.createElement('button');b.textContent=f==='ext'?'Ext':f.replace('-','−');if(f==='ext')b.className='ext';
  b.setAttribute('aria-label',f==='ext'?'Exterior':'Piso '+f);b.onclick=()=>setFloor(f);nav.appendChild(b)});

// true si el piso tiene salas dibujadas
function hasRooms(f){return (FLOORS_DATA[f]||[]).some(r=>!selB||r.building===selB)}

// pinta el selector de pisos (cual esta activo y cuales tienen plano)
function paintFloors(){[...nav.children].forEach((b,i)=>{const f=FLOORS[i];b.setAttribute('aria-pressed',f===floor);
  b.classList.toggle('empty',f!=='ext'&&!hasRooms(f));b.hidden=!!selB&&f!=='ext'&&!(BFLOORS[selB]||[]).includes(f)})}

// aviso cuando un piso todavia no tiene plano
function updNotice(){const n=document.getElementById('notice');
  if(floor!=='ext'&&!hasRooms(floor)){n.hidden=false;n.textContent=(selB?selB+', ':'')+'piso '+floor.replace('-','−')+': todavía no hay plano de este piso.'}else n.hidden=true}

// cambiar de piso
function setFloor(f){floor=f;sel=null;closeSheet(true);document.getElementById('chipIn').hidden=f!=='ext';paintFloors();updNotice();
  rebuild()}
paintFloors();

/* ---------- hoja de la sala ---------- */

// abrir la hoja de una sala con el boton "reportar aqui"
function openRoom(r){if(r.id&&r.pts&&!r.group&&(GROUPS[floor]||[]).includes(r)){const c=centroid(r.pts);animTo({x:c[0],y:c[1],z:3});return}sel=r;rebuild();
  document.getElementById('sTitle').textContent=r.label?(/^[A-Z]\d+$/.test(r.label)?'Sala '+r.label:r.label):'Sala sin nombre';
  document.getElementById('sSub').textContent=(r.building?r.building+' · ':'')+'Piso '+floor;
  document.getElementById('sDemo').hidden=true;document.getElementById('sheet').classList.add('open')}

// cerrar la hoja de la sala
function closeSheet(keep){document.getElementById('sheet').classList.remove('open');if(!keep){sel=null;rebuild()}}
document.getElementById('sClose').onclick=()=>closeSheet();
document.getElementById('sReport').onclick=()=>{document.getElementById('sDemo').hidden=false};

/* ---------- búsqueda ---------- */
const norm=s=>(s||'').normalize('NFD').replace(/[̀-ͯ]/g,'').toLowerCase().replace(/\s+/g,'');
const IDX=[];Object.entries(FLOORS_DATA).forEach(([f,rs])=>rs.forEach((r,i)=>{if(r.label)IDX.push({f,i,r,k:norm(r.label)})}));
const q=document.getElementById('q'),res=document.getElementById('res');

// muestra los resultados del buscador
function show(list){res.innerHTML='';res.hidden=false;
  if(!list.length){const li=document.createElement('li');li.className='none';li.textContent='No encontré esa sala.';res.appendChild(li);return}
  list.slice(0,12).forEach(it=>{const li=document.createElement('li');const b=document.createElement('button');b.type='button';b.textContent=it.r.label;
    const sp=document.createElement('span');sp.textContent=it.r.ext?'Exterior del campus':(it.r.building?it.r.building+' · ':'')+'Piso '+it.f;b.appendChild(sp);b.onclick=()=>go(it);li.appendChild(b);res.appendChild(li)})}
q.addEventListener('input',()=>{const k=norm(q.value);if(!k){res.hidden=true;return}
  show(IDX.filter(it=>it.k.includes(k)).sort((a,b)=>(a.k.startsWith(k)?0:1)-(b.k.startsWith(k)?0:1)||a.k.localeCompare(b.k)))});
q.addEventListener('keydown',e=>{if(e.key==='Enter'){const b=res.querySelector('button');if(b)b.click()}if(e.key==='Escape')res.hidden=true});
document.addEventListener('pointerdown',e=>{if(!e.target.closest('.search'))res.hidden=true});

// ir a la sala elegida en el buscador
function go(it){res.hidden=true;q.value=it.r.label;q.blur();if(selB&&selB!==it.r.building)selectBuilding(null);if(floor!==it.f)setFloor(it.f);
  const c=centroid(it.r.pts);animTo({x:c[0],y:c[1],z:2.6});openRoom(it.r)}

/* ---------- simulación de ubicación (el gps real se conecta en la app) ---------- */
const ROUTE=[[230,1300],[300,1215],[600,1205],[790,1205],[790,1000],[790,820],[1040,800],[1040,560],[1370,560],[1370,800]];
let walkT=null;
document.getElementById('walk').onclick=e=>{if(walkT){clearInterval(walkT);walkT=null;me=null;e.target.textContent='Simular mi ubicación';dirty=true;return}
  let seg=0,t=0;me={x:ROUTE[0][0],y:ROUTE[0][1]};e.target.textContent='Detener simulación';animTo({x:me.x,y:me.y,z:Math.max(cam.z,2)});
  walkT=setInterval(()=>{const a=ROUTE[seg],b=ROUTE[seg+1];const L=Math.hypot(b[0]-a[0],b[1]-a[1]);t+=3/L;
    if(t>=1){t=0;seg++;if(seg>=ROUTE.length-1)seg=0}const A=ROUTE[seg],B=ROUTE[seg+1];me={x:A[0]+(B[0]-A[0])*t,y:A[1]+(B[1]-A[1])*t};
    cam.x+=(me.x-cam.x)*0.08;cam.y+=(me.y-cam.y)*0.08;dirty=true},40)};

/* ---------- categorías y pines (datos de ejemplo) ---------- */
const CATS=[
 {id:'bano',n:'Baños',c:'#0C8599',i:'M6 3h5v7H6z M4 10h14v1a6 6 0 0 1-6 6h-3l-1 4h7'},
 {id:'agua',n:'Agua y goteras',c:'#1C7ED6',i:'M12 3s6 6.2 6 10.5a6 6 0 0 1-12 0C6 9.2 12 3 12 3z'},
 {id:'clima',n:'Climatización',c:'#E8590C',i:'M10 13.5V5a2 2 0 0 1 4 0v8.5a4 4 0 1 1-4 0z M12 9v7'},
 {id:'luz',n:'Iluminación',c:'#F59F00',k:'#2B2100',i:'M9.5 18h5 M10 21h4 M12 3a6 6 0 0 0-3.5 10.9c.6.5 1 1.2 1 2.1h5c0-.9.4-1.6 1-2.1A6 6 0 0 0 12 3z'},
 {id:'elec',n:'Electricidad y enchufes',c:'#7048E8',i:'M13 3L5 14h6l-1 7 8-11h-6l1-7z'},
 {id:'wifi',n:'Internet y WiFi',c:'#364FC7',i:'M2.5 9a14 14 0 0 1 19 0 M5.5 12.5a9.5 9.5 0 0 1 13 0 M8.8 16a5 5 0 0 1 6.4 0 M12 19.5h.01'},
 {id:'equipo',n:'Proyector y equipos',c:'#AE3EC9',i:'M3 4h18v12H3z M8 20h8 M12 16v4'},
 {id:'mueble',n:'Mobiliario',c:'#8D5524',i:'M7 3h10v9H7z M5 12h14 M8 12v9 M16 12v9'},
 {id:'puerta',n:'Puertas, ventanas y cerraduras',c:'#D6336C',i:'M6 3h12v18H6z M14.5 12h.01 M3 21h18'},
 {id:'danos',n:'Daños en muro, techo o piso',c:'#C92A2A',i:'M4 4h16v16H4z M12 4l-2 5 3 3-2 4 1 4'},
 {id:'aseo',n:'Aseo y basura',c:'#2B8A3E',i:'M4 7h16 M9 7V4h6v3 M6 7l1 14h10l1-14 M10 11v6 M14 11v6'},
 {id:'verde',n:'Áreas verdes y exteriores',c:'#5C940D',i:'M12 21v-6 M12 3a5 5 0 0 0-5 5 4 4 0 0 0 1 7h8a4 4 0 0 0 1-7 5 5 0 0 0-5-5z'},
 {id:'ascensor',n:'Ascensor, escaleras y rampas',c:'#495057',i:'M3 20h5v-4h4v-4h4V8h5'},
 {id:'otro',n:'Otro',c:'#868E96',i:'M6 12h.01 M12 12h.01 M18 12h.01'}];
const CAT=Object.fromEntries(CATS.map(c=>[c.id,c]));CATS.forEach(c=>c.p=new Path2D(c.i));
const ESTADO={pendiente:'Pendiente',en_proceso:'En proceso',resuelto:'Resuelto'};
const REPORTS=leerDato("d-reportes");
function edificioEn(p,f){const b=S.buildings.find(b=>!b.bridge&&/^Edificio/.test(b.name)&&inPoly(p,(b.fp&&f&&b.fp[f])||b.pts));return b?b.name:''}
REPORTS.forEach(r=>{if(!r.b&&r.f!=='ext'&&r.x!=null)r.b=edificioEn([r.x,r.y],r.f);if(r.salapk!=null)r.r=(FLOORS_DATA[r.f]||[]).find(o=>o.pk===r.salapk);if(r.f==='ext'||r.x!=null)return;const room=(FLOORS_DATA[r.f]||[]).find(o=>o.label===r.room&&o.building===r.b);
  if(room){r.r=room;[r.x,r.y]=centroid(room.pts)}else{const lb=S.labels.find(l=>l[0]===r.b);r.x=lb[1];r.y=lb[2]}});
const catOn=new Set(CATS.map(c=>c.id));let soloActivos=true,selRep=null,PINS=[];

// true si un reporte se muestra segun los filtros
function repVisible(r){return catOn.has(r.cat)&&(!soloActivos||r.e!=='resuelto')}
function pinsNow(){return REPORTS.filter(repVisible).filter(r=>{
  if(floor==='ext')return !selB||r.b===selB||r.f==='ext';
  return r.f===floor&&(r.r||r.x!=null)&&(!selB||r.b===selB)})}
function pinZ(r){if(r.f==='ext')return 0;if(floor==='ext')return (BH[r.b]||2)*FH+1;return 5+(r.r?rh(r.r):0)}
// de lejos: un pin amarillo por edificio con el total de reportes
let agrupado=true;
function drawCluster(cx,cy,n,s){const R=(15+Math.min(n,20)*0.35)*s,hy=cy-30*s;ctx.save();
  ctx.fillStyle='rgba(0,0,0,.22)';ctx.beginPath();ctx.ellipse(cx,cy,8*s,3*s,0,0,7);ctx.fill();
  ctx.beginPath();ctx.moveTo(cx,cy-1);ctx.bezierCurveTo(cx-4*s,cy-8*s,cx-R,hy+R*0.55,cx-R,hy);ctx.arc(cx,hy,R,Math.PI,0);
  ctx.bezierCurveTo(cx+R,hy+R*0.55,cx+4*s,cy-8*s,cx,cy-1);ctx.closePath();
  ctx.fillStyle='#FFC72C';ctx.fill();
  ctx.lineWidth=2.6;ctx.strokeStyle='#fff';ctx.stroke();
  ctx.fillStyle='#2B2100';ctx.font=`800 ${Math.round((n>9?14:16)*s)}px -apple-system,BlinkMacSystemFont,Inter,sans-serif`;ctx.textAlign='center';ctx.textBaseline='middle';
  ctx.fillText(String(n),cx,hy+0.5);ctx.restore();return {x:cx,y:hy,R:R+5}}
let PINA=null,PINR=null;function pinPop(){if(PINR!==selRep){PINR=selRep;PINA=reduceMotion()?null:performance.now()}if(!PINA)return 1.25;const t=Math.min(1,(performance.now()-PINA)/420);if(t>=1){PINA=null;return 1.25}dirty=true;
  const c1=1.7,c3=c1+1,e=1+c3*Math.pow(t-1,3)+c1*Math.pow(t-1,2);return 1+0.25*e}

// dibuja los pines de los reportes (agrupados en amarillo al alejar)
function drawPins(){PINS=[];
  if(agrupado&&cam.z>1.45)agrupado=false;else if(!agrupado&&cam.z<1.25)agrupado=true;
  if(agrupado){const grupos={};const sueltos=[];
    pinsNow().forEach(r=>{if(r.b)(grupos[r.b]=grupos[r.b]||[]).push(r);else sueltos.push(r)});
    const zs=Math.max(.85,Math.min(1.15,cam.z));
    Object.entries(grupos).map(([b,rs])=>{const lb=S.labels.find(l=>l[0]===b);const p=P(lb[1],lb[2],floor==='ext'?(BH[b]||2)*FH+1:17);return {b,rs,p}})
      .sort((a,b)=>a.p[2]-b.p[2]).forEach(({b,rs,p})=>{if(p[0]<-40||p[0]>W+40||p[1]<-60||p[1]>H+40)return;
        const o=drawCluster(p[0],p[1]-18*zs,rs.length,zs);PINS.push({cluster:b,...o})});
    if(!sueltos.length)return}
  const list=(agrupado?pinsNow().filter(r=>!r.b):pinsNow()).map(r=>{const p=P(r.x,r.y,pinZ(r));return {r,p}}).sort((a,b)=>a.p[2]-b.p[2]);
  const zs=Math.max(.8,Math.min(1.25,cam.z));
  const placed=[];
  list.forEach(({r,p})=>{const c=CAT[r.cat],s=(r===selRep?pinPop():1)*zs*(0.7+0.3*LA)*(1+Math.min(r.ap,20)/80);let x=p[0];const y=p[1];
    // si dos pines quedan encima, se corren a un lado
    for(const k of [0,1,-1,2,-2,3,-3]){const nx=p[0]+k*24*s;if(!placed.some(q=>Math.hypot(q[0]-nx,q[1]-y)<22*s)){x=nx;break}}placed.push([x,y]);
    if(x<-40||x>W+40||y<-60||y>H+40)return;
    const R=13*s,hy=y-27*s;ctx.save();ctx.globalAlpha=r.e==='resuelto'?0.55:1;
    ctx.fillStyle='rgba(0,0,0,.22)';ctx.beginPath();ctx.ellipse(x,y,7*s,2.8*s,0,0,7);ctx.fill();
    ctx.beginPath();ctx.moveTo(x,y-1);ctx.bezierCurveTo(x-4*s,y-8*s,x-R,hy+R*0.55,x-R,hy);ctx.arc(x,hy,R,Math.PI,0);
    ctx.bezierCurveTo(x+R,hy+R*0.55,x+4*s,y-8*s,x,y-1);ctx.closePath();
    ctx.fillStyle=c.c;ctx.fill();
    ctx.lineWidth=2.4;ctx.strokeStyle='#fff';ctx.stroke();
    ctx.translate(x-8.4*s,hy-8.4*s);ctx.scale(0.7*s,0.7*s);ctx.strokeStyle=c.k||'#fff';ctx.lineWidth=r.cat==='otro'?4.2:2.3;ctx.lineCap='round';ctx.lineJoin='round';ctx.stroke(c.p);
    ctx.setTransform(dpr,0,0,dpr,0,0);
    if(r.e!=='pendiente'){const bx=x+R*0.78,by=hy-R*0.78;ctx.fillStyle=r.e==='resuelto'?'#2F9E44':'#1971C2';ctx.beginPath();ctx.arc(bx,by,6.5*s,0,7);ctx.fill();
      ctx.lineWidth=2;ctx.strokeStyle='#fff';ctx.stroke();ctx.beginPath();ctx.lineWidth=1.7;
      if(r.e==='resuelto'){ctx.moveTo(bx-3*s,by);ctx.lineTo(bx-0.8*s,by+2.2*s);ctx.lineTo(bx+3*s,by-2*s)}else{ctx.moveTo(bx,by-3*s);ctx.lineTo(bx,by);ctx.lineTo(bx+2.4*s,by+1.4*s)}ctx.stroke()}
    ctx.restore();PINS.push({r,x,y:hy,R:R+4})})}
const _drawOverlay=drawOverlay;drawOverlay=function(){_drawOverlay();drawPins()};
const _tap=tap;tap=function(e){const rc=cv.getBoundingClientRect();const x=e.clientX-rc.left,y=e.clientY-rc.top;
  for(let i=PINS.length-1;i>=0;i--){const o=PINS[i];if(Math.hypot(x-o.x,y-o.y)<o.R){
    if(o.cluster){const lb=S.labels.find(l=>l[0]===o.cluster);animTo({x:lb[1],y:lb[2],z:Math.max(1.8,cam.z)});return}
    openReport(o.r);return}}_tap(e)};
const rsheet=document.getElementById('rsheet');
const svgIcon=(c,size)=>`<svg viewBox="0 0 24 24" width="${size}" height="${size}" stroke="${c.k||'#fff'}" aria-hidden="true"><path d="${c.i}"${c.id==='otro'?' stroke-width="4"':''}/></svg>`;

// abrir la hoja de un reporte
function openReport(r){selRep=r;closeSheet(true);const c=CAT[r.cat];
  document.getElementById('rTitle').textContent=r.t;
  document.getElementById('rSub').textContent=r.f==='ext'?'Exterior del campus':[r.room,r.b,'Piso '+r.f.replace('-','−')].filter(Boolean).join(' · ');
  document.getElementById('rTags').innerHTML=`<span class="tag" style="background:${c.c};color:${c.k||'#fff'}">${svgIcon(c,16)}${c.n}</span><span class="est ${r.e}">${ESTADO[r.e]}</span><span class="apo">▲ ${r.ap} apoyos</span>`;
  document.getElementById('rDemo').hidden=true;rsheet.classList.add('open');animTo({x:r.x,y:r.y});dirty=true}

// cerrar la hoja de un reporte
function closeReport(){rsheet.classList.remove('open');selRep=null;dirty=true}
document.getElementById('rClose').onclick=closeReport;
document.getElementById('rApoyo').onclick=()=>{if(selRep&&!selRep.yo){selRep.yo=true;selRep.ap++;openReport(selRep)}document.getElementById('rDemo').hidden=false};
const _openRoom=openRoom;openRoom=function(r){closeReport();_openRoom(r)};
/* panel de categorías */
const catbtn=document.getElementById('catbtn'),cats=document.getElementById('cats'),catlist=document.getElementById('catlist');
let catOpen=null,cfgMode=false;
const lugar=r=>r.f==='ext'?'Exterior del campus':`${r.room} · ${r.b.replace('Edificio ','Edif. ')} · Piso ${r.f}`;

// ir al lugar de un reporte (cambia de edificio y piso si hace falta)
function goReport(r){cats.hidden=true;catbtn.setAttribute('aria-expanded',false);catOn.add(r.cat);
  if(r.f==='ext'){if(floor!=='ext')setFloor('ext')}else{if(selB!==r.b)selectBuilding(r.b);if(floor!==r.f)setFloor(r.f)}
  setTimeout(()=>{openReport(r);animTo({x:r.x,y:r.y,z:Math.max(cam.z,2.4)})},floor===r.f?0:420);dirty=true}

// panel de tipos de reporte: ver por tipo u ocultar pines
function paintCats(){catlist.innerHTML='';const reps=c=>REPORTS.filter(r=>r.cat===c.id&&(!soloActivos||r.e!=='resuelto')).sort((a,b)=>b.ap-a.ap);
  CATS.forEach(c=>{const L=reps(c),n=L.length;
    const b=document.createElement('button');b.className='cat'+(n||cfgMode?'':' zero');b.type='button';b.setAttribute('aria-pressed',catOn.has(c.id));
    if(cfgMode){b.innerHTML=`<span class="ic" style="background:${c.c}">${svgIcon(c,19)}</span><span class="nm">${c.n}</span><span class="ct">${n}</span><span class="sw" aria-hidden="true"></span>`;
      b.setAttribute('aria-label',`${c.n}: ${catOn.has(c.id)?'visible':'oculto'} en el mapa`);
      b.onclick=()=>{catOn.has(c.id)?catOn.delete(c.id):catOn.add(c.id);paintCats();dirty=true}}
    else{b.setAttribute('aria-expanded',catOpen===c.id);
      b.innerHTML=`<span class="ic" style="background:${c.c}">${svgIcon(c,19)}</span><span class="nm">${c.n}</span>${catOn.has(c.id)?'':'<span class="eye">oculto</span>'}<span class="ct">${n}</span><svg class="chev" viewBox="0 0 24 24" aria-hidden="true"><path d="M9 6l6 6-6 6"/></svg>`;
      b.onclick=()=>{if(!n)return;catOpen=catOpen===c.id?null:c.id;paintCats()}}
    catlist.appendChild(b);
    if(!cfgMode&&catOpen===c.id&&n){const ul=document.createElement('ul');ul.className='creps';
      L.forEach(r=>{const li=document.createElement('li'),bt=document.createElement('button');bt.type='button';
        bt.innerHTML=`<span><b></b><small></small></span><span class="ap">▲ ${r.ap}</span>`;bt.querySelector('b').textContent=r.t;bt.querySelector('small').textContent=lugar(r);
        bt.onclick=()=>goReport(r);li.appendChild(bt);ul.appendChild(li)});catlist.appendChild(ul)}});
  document.getElementById('catn').textContent=REPORTS.filter(repVisible).length}
const cCfg=document.getElementById('cCfg');
cCfg.onclick=()=>{cfgMode=!cfgMode;cCfg.setAttribute('aria-pressed',cfgMode);cats.classList.toggle('cfgmode',cfgMode);
  document.getElementById('cTitle').textContent=cfgMode?'Mostrar en el mapa':'Reportes';
  document.getElementById('cSub').textContent=cfgMode?'Elige qué tipos de reporte aparecen como pines.':'Toca un tipo para ver sus reportes y uno para ir a su lugar. Datos de ejemplo.';paintCats()};
catbtn.onclick=()=>{const open=cats.hidden;cats.hidden=!open;catbtn.setAttribute('aria-expanded',open)};
document.getElementById('cAll').onclick=()=>{CATS.forEach(c=>catOn.add(c.id));paintCats();dirty=true};
document.getElementById('cNone').onclick=()=>{catOn.clear();paintCats();dirty=true};
const eAct=document.getElementById('eAct'),eTodos=document.getElementById('eTodos');
eAct.onclick=()=>{soloActivos=true;eAct.setAttribute('aria-pressed',true);eTodos.setAttribute('aria-pressed',false);paintCats();dirty=true};
eTodos.onclick=()=>{soloActivos=false;eTodos.setAttribute('aria-pressed',true);eAct.setAttribute('aria-pressed',false);paintCats();dirty=true};
document.addEventListener('keydown',e=>{if(e.key==='Escape'){cats.hidden=true;catbtn.setAttribute('aria-expanded',false)}});
paintCats();
// solo modo claro
setTheme(false);document.documentElement.dataset.theme='light';rebuild();
const _setFloor=setFloor;setFloor=function(f){closeReport();_setFloor(f)};
const _selB=selectBuilding;selectBuilding=function(n){closeReport();_selB(n)};

/* ---------- gps real (prueba) ---------- */
// conversión gps -> plano del mapa, calculada con los edificios de openstreetmap (error aprox. 5-10 m)
const GEO={lat0:-33.4915,lon0:-70.6185,KX:111320*Math.cos(33.49*Math.PI/180),KY:110574,a:-0.038112,b:-0.167138,tx:-147.443,ty:65.849,s:0.17143,dx:118,dy:15}; // dx,dy: ajuste con la entrada principal medida en terreno (2 lecturas)

// pasa la posicion del gps (latitud y longitud) al plano del mapa
function geoToMap(lat,lon){const u=(lon-GEO.lon0)*GEO.KX-GEO.tx,v=-(lat-GEO.lat0)*GEO.KY-GEO.ty,d=GEO.a*GEO.a+GEO.b*GEO.b;
  return [(GEO.a*u+GEO.b*v)/d+GEO.dx,(-GEO.b*u+GEO.a*v)/d+GEO.dy]}
const gpsBtn=document.getElementById('gps'),gpsInfo=document.getElementById('gpsinfo');let gpsW=null,gpsFirst=true;

// mensaje del gps
function gpsMsg(h){gpsInfo.hidden=!h;gpsInfo.innerHTML=h||''}

// apaga el gps
function gpsStop(){if(gpsW!==null)navigator.geolocation.clearWatch(gpsW);gpsW=null;gpsBtn.setAttribute('aria-pressed',false);if(me&&me.acc)me=null;gpsMsg('');dirty=true}
gpsBtn.onclick=()=>{
  if(gpsW!==null){gpsStop();return}
  if(walkT){document.getElementById('walk').click()}
  if(!('geolocation' in navigator)){gpsMsg('Este navegador no permite usar la ubicación.');return}
  if(!window.isSecureContext){gpsMsg('La ubicación solo funciona con una dirección segura (https).');return}
  gpsBtn.setAttribute('aria-pressed',true);gpsFirst=true;gpsMsg('Buscando tu ubicación…');
  gpsW=navigator.geolocation.watchPosition(pos=>{
    const {latitude:la,longitude:lo,accuracy:ac}=pos.coords;const [x,y]=geoToMap(la,lo);
    const fuera=x<-150||x>S.w+150||y<-150||y>S.h+150;
    me={x,y,acc:ac};dirty=true;
    gpsMsg(`<b>Precisión: ±${Math.round(ac)} m</b>${ac>25?' · señal débil':''}<br>${la.toFixed(6)}, ${lo.toFixed(6)}${fuera?'<br>Estás fuera del campus':''}`);
    if(gpsFirst&&!fuera){gpsFirst=false;animTo({x,y,z:Math.max(cam.z,2)})}
  },err=>{
    const m={1:'No diste permiso para usar tu ubicación. Puedes activarlo en los ajustes del navegador.',2:'No se pudo obtener tu ubicación. Prueba al aire libre.',3:'La ubicación tardó demasiado. Inténtalo de nuevo.'}[err.code]||'No se pudo obtener tu ubicación.';
    gpsStop();gpsMsg(m+(err.code===1?'<br>Si abriste el mapa dentro de Claude, puede que la vista no permita el GPS.':''));
  },{enableHighAccuracy:true,maximumAge:2000,timeout:20000});
};

/* ===== propuesta v2 ===== */
// accesos rápidos y búsquedas recientes (se guardan solo en este dispositivo)
const RKEY='upin_recientes';const getRec=()=>{try{return JSON.parse(localStorage.getItem(RKEY))||[]}catch(e){return []}};
const putRec=l=>{try{let a=getRec().filter(x=>x!==l);a.unshift(l);localStorage.setItem(RKEY,JSON.stringify(a.slice(0,5)))}catch(e){}};
document.querySelectorAll('.quick button').forEach(b=>b.onclick=()=>{q.value=b.dataset.q;q.dispatchEvent(new Event('input'));q.focus()});
q.addEventListener('focus',()=>{if(q.value)return;const rec=getRec().map(l=>IDX.find(it=>it.r.label===l)).filter(Boolean);if(!rec.length)return;
  show(rec);const h=document.createElement('li');h.className='rec';h.textContent='Recientes';res.prepend(h)});
const _go=go;go=function(it){putRec(it.r.label);_go(it)};
// cambio de piso con un fundido suave
// cambio de piso: el piso actual baja y el nuevo sube desde el suelo
const _sf2=setFloor;
const eIn=t=>t*t*(3-2*t), eOut=t=>1-Math.pow(1-t,4);

// animacion al cambiar de piso (el piso baja o sube)
function floorStep(now){const a=FA;let t=Math.min(1,(now-a.t0)/a.d);
  if(a.ph==='out'){const k=1-eIn(t);HK=HK0*(a.h0/HK0)*k+0.001;LA=a.l0*k;
    if(t>=1){_sf2(a.f);HK=0.001;LA=0;FA={ph:'in',t0:now,d:520,f:a.f}}}
  else{const k=eOut(t);HK=HK0*k+0.001;LA=Math.max(0,(t-0.35)/0.65);LA=LA*LA*(3-2*LA);
    if(t>=1){HK=HK0;LA=1;FA=null}}
  dirty=true}
const reduceMo=reduceMotion;
// desde código (buscador, ver salas): cambia al tiro y el piso sube
setFloor=function(f){FA=null;_sf2(f);if(!reduceMo()){HK=0.001;LA=0;FA={ph:'in',t0:performance.now(),d:520,f}}};
// desde los botones de piso: el actual baja, luego el nuevo sube
function floorTap(f){if(f===floor&&!FA)return;if(reduceMo()){FA=null;_sf2(f);return}
  FA={ph:'out',t0:performance.now(),d:170,f,h0:HK,l0:LA};
  [...nav.children].forEach((b,i)=>b.setAttribute('aria-pressed',FLOORS[i]===f))}
[...nav.children].forEach((b,i)=>b.onclick=()=>floorTap(FLOORS[i]));
// brújula: un toque vuelve al norte; si ya está al norte, alterna 2.5d / 2d
document.getElementById('compass').onclick=()=>{if(Math.abs(cam.b)>0.02)animTo({b:0});else (cam.p>0.1?m2d:m25).click()};
// hoja: tocar la barrita la sube o baja
document.querySelectorAll('.sheet .grab').forEach(g=>g.onclick=()=>g.parentElement.classList.toggle('full'));
// tarjeta de sala: tipo de espacio + reportes activos ahí
const TIPO={sala:'Sala de clases',depto:'Oficina / departamento',aula:'Auditorio',servicio:'Servicio',cafe:'Cafetería',gimnasio:'Deporte',casino:'Comida',patio:'Espacio abierto',rampa:'Acceso'};
function repItem(r){const c=CAT[r.cat];return `<li><span class="ic" style="background:${c.c}">${svgIcon(c,17)}</span><span><b>${r.t}</b><small>${c.n} · ${ESTADO[r.e]}</small></span><span class="ap">▲ ${r.ap}</span></li>`}
const _or=openRoom;openRoom=function(r){_or(r);if(sel!==r)return;
  const reps=REPORTS.filter(x=>x.r===r&&x.e!=='resuelto');const sh=document.getElementById('sheet');sh.classList.remove('full');
  let m=sh.querySelector('.meta');if(!m){m=document.createElement('div');m.className='meta';document.getElementById('sSub').after(m)}
  m.innerHTML=`<span class="tag2">${rtype(r)==='bano'?'Baño':rtype(r)==='esc'?'Escalera':TIPO[r.kind]||'Espacio'}</span>`+(reps.length?`<span class="tag2 warn">${reps.length} ${reps.length>1?'reportes activos':'reporte activo'}</span>`:`<span class="tag2 ok">Sin reportes activos</span>`);
  let l=sh.querySelector('.replist');if(l)l.remove();if(reps.length){l=document.createElement('ul');l.className='replist';l.innerHTML=reps.map(repItem).join('');sh.appendChild(l)}};
// tarjeta de edificio: pisos y reportes
const _sb=selectBuilding;selectBuilding=function(n){_sb(n);if(!n)return;const nm=document.getElementById('chipName');
  const reps=REPORTS.filter(r=>r.b===n&&r.e!=='resuelto').length,fl=(BFLOORS[n]||[]).length;
  let w=chip.querySelector('.cinfo');if(!w){w=document.createElement('span');w.className='cinfo';nm.before(w);w.appendChild(nm);w.appendChild(document.createElement('small'))}
  w.querySelector('small').textContent=`${fl} ${fl===1?'piso':'pisos'} · ${reps?reps+' '+(reps>1?'reportes activos':'reporte activo'):'sin reportes activos'}`};

/* ===== movimiento de la interfaz ===== */
(function(){
const RM=reduceMotion;
// indicador que se desliza en el selector de pisos y en 2.5d/2d

// indicador que se desliza en el selector de pisos y en 2d / 2.5d
function slider(box,sel){const ind=document.createElement('span');ind.className='ind';box.append(ind);let first=true;
  const upd=()=>{const b=box.querySelector(sel+'[aria-pressed="true"]');if(!b||b.hidden||!b.offsetParent){ind.style.opacity=0;return}
    ind.style.opacity=1;if(first||RM())ind.style.transition='none';
    ind.style.transform=`translate(${b.offsetLeft}px,${b.offsetTop}px)`;ind.style.width=b.offsetWidth+'px';ind.style.height=b.offsetHeight+'px';
    if(first||RM()){ind.offsetWidth;ind.style.transition='';first=false}};
  new MutationObserver(upd).observe(box,{attributes:true,subtree:true,attributeFilter:['aria-pressed','hidden']});
  new ResizeObserver(upd).observe(box);upd()}
slider(nav,'button');slider(document.querySelector('.mode'),'button');
// resultados del buscador: entran suave solo al abrir la lista
const _show=show;show=function(l){const was=res.hidden;_show(l);if(was&&!RM()){res.classList.remove('enter');res.offsetWidth;res.classList.add('enter')}};
// hojas: cambiar de sala con la hoja abierta hace un fundido corto del contenido
['sheet','rsheet'].forEach(id=>{const sh=document.getElementById(id);
  new MutationObserver(()=>{}).observe(sh,{attributes:true});
  // arrastrar la hoja: hacia abajo la cierra, hacia arriba la agranda
  let y0=null,t0=0,dy=0,ys=[];
  sh.addEventListener('pointerdown',e=>{if(e.target.closest('button,a,input,.replist')||sh.scrollTop>0)return;y0=e.clientY;t0=performance.now();dy=0;ys=[[t0,y0]];sh.setPointerCapture(e.pointerId);sh.classList.add('dragging')});
  sh.addEventListener('pointermove',e=>{if(y0===null)return;dy=e.clientY-y0;const t=performance.now();ys.push([t,e.clientY]);while(ys.length>2&&t-ys[0][0]>90)ys.shift();
    const v=dy>0?dy:-Math.pow(-dy,0.72);sh.style.transform=`translateY(${v}px)`});
  const end=e=>{if(y0===null)return;sh.classList.remove('dragging');const t=performance.now(),f=ys[0];const vel=(e.clientY-f[1])/Math.max(1,t-f[0]);
    y0=null;sh.style.transform='';
    if(Math.abs(dy)<6){if(e.target.closest('.grab'))sh.classList.toggle('full');return}
    if(dy>110||vel>0.55){if(sh.classList.contains('full')&&dy<220&&vel<1.2){sh.classList.remove('full');return}
      if(id==='sheet')closeSheet();else closeReport()}
    else if(dy<-40||vel<-0.5)sh.classList.add('full')};
  sh.addEventListener('pointerup',end);sh.addEventListener('pointercancel',end)});
document.querySelectorAll('.sheet .grab').forEach(g=>g.onclick=null);

// cambio suave del contenido de una hoja
function swap(sh){if(RM())return;sh.classList.remove('swap');sh.offsetWidth;sh.classList.add('swap')}
const _or2=openRoom;openRoom=function(r){const sh=document.getElementById('sheet');const was=sh.classList.contains('open');const prev=sel;_or2(r);if(was&&prev!==sel)swap(sh)};
const _rep2=openReport;openReport=function(r){const was=rsheet.classList.contains('open');const prev=selRep;_rep2(r);if(was&&prev!==r)swap(rsheet)};
// apoyar: el botón da un pequeño salto
document.getElementById('rApoyo').addEventListener('click',e=>{if(RM())return;const b=e.currentTarget;b.classList.remove('pop');b.offsetWidth;b.classList.add('pop')});
// la tarjeta del edificio se acomoda suave cuando cambia de edificio
const _sb3=selectBuilding;selectBuilding=function(n){const was=!chip.hidden,prev=selB;_sb3(n);if(was&&n&&prev!==n)swap(chip)};
})();

/* ===== estética v3: leyenda y celular ===== */
(function(){const lg=document.getElementById('legend');const lb=document.getElementById('legBtn');
  lb.onclick=()=>{const o=lg.classList.toggle('open');lb.setAttribute('aria-expanded',o)};
  lg.hidden=false;
  const _sb4=selectBuilding;selectBuilding=function(n){_sb4(n);document.body.classList.toggle('bsel',!!n)};
})();

/* medidor de fps: abrir el enlace con #fps al final */
(function(){if(!/fps/.test(location.hash+location.search))return;const d=document.createElement('div');d.style.cssText='position:fixed;left:50%;transform:translateX(-50%);bottom:34px;z-index:99;background:rgba(0,0,0,.75);color:#fff;font:600 12px ui-monospace,monospace;padding:6px 8px;border-radius:8px;pointer-events:none';document.body.appendChild(d);
  let n=0,t0=performance.now(),worst=0,last=t0;(function f(t){n++;worst=Math.max(worst,t-last);last=t;if(t-t0>=1000){d.textContent=`${Math.round(n*1000/(t-t0))} FPS · peor ${Math.round(worst)} ms · calidad ${Math.round(GQ*100)}% · ${glc.width}×${glc.height}`;n=0;t0=t;worst=0}requestAnimationFrame(f)})(t0)})();


/* ===== estética 2: brújula solo al girar, botón reportar ===== */
(function(){
const cp=document.getElementById('compass').parentElement;let off=null;
setInterval(()=>{const a=((cam.b%(2*Math.PI))+2*Math.PI)%(2*Math.PI),o=Math.min(a,2*Math.PI-a)<0.6;if(o!==off){off=o;cp.classList.toggle('off',o)}},150);
const fab=document.getElementById('fab'),pick=document.getElementById('pick'),tx=document.getElementById('pickTx');let picking=false;

// modo "reportar": esperar que se toque el lugar del problema
function setPick(on){picking=on;fab.setAttribute('aria-pressed',on);fab.querySelector('span').textContent=on?'Cancelar':'Reportar';pick.hidden=!on;
  if(on){closeSheet(true);tx.textContent=floor==='ext'?'Elige un edificio y toca la sala del problema':'Toca la sala donde está el problema'}}
fab.onclick=()=>setPick(!picking);
document.getElementById('pickX').onclick=()=>setPick(false);
const _sf=setFloor;setFloor=function(f){_sf(f);if(picking)tx.textContent=f==='ext'?'Elige un edificio y toca la sala del problema':'Toca la sala donde está el problema'};
const _or=openRoom;openRoom=function(r){_or(r);if(picking&&sel===r){setPick(false);setTimeout(()=>document.getElementById('sReport').click(),350)}};
})();


/* ===== pisos plegables (abren hacia arriba y abajo por igual); botón de perfil ===== */
(function(){
const nav=document.getElementById('floors'),tog=document.getElementById('fltog'),tx=document.getElementById('fltx');

// muestra el piso actual en el boton de pisos
function syncTog(){tx.textContent=floor==='ext'?'Ext':floor.replace('-','−')}
const _pf=paintFloors;paintFloors=function(){_pf();syncTog()};syncTog();
let open=false,closeT=0;

// abre o cierra la lista de pisos
function setOpen(o){open=o;clearTimeout(closeT);nav.classList.toggle('fcol',!o);tog.setAttribute('aria-expanded',o);if(o){const b=nav.querySelector('button[aria-pressed="true"]');b&&b.focus({preventScroll:true})}}
const desk=()=>matchMedia('(min-width:701px)').matches;
tog.onclick=()=>setOpen(desk()?!open:true);
if(desk()){open=true;nav.classList.remove('fcol');tog.setAttribute('aria-expanded',true)}
nav.addEventListener('click',e=>{if(desk())return;if(e.target.closest('button')){clearTimeout(closeT);closeT=setTimeout(()=>setOpen(false),550)}});
document.getElementById('cv').addEventListener('pointerdown',()=>{if(open&&!desk())setOpen(false)});
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&open){setOpen(false);tog.focus()}});
const pr=document.getElementById('prof');pr.onclick=()=>{const n=document.getElementById('notice');n.hidden=false;n.textContent='Mi perfil se abre aquí cuando lo pasemos a la app.';clearTimeout(pr._t);pr._t=setTimeout(()=>updNotice(),2200)};
})();


/* ===== ubicación automática, carita para ir a mi ubicación, encuadre de sala ===== */
(function(){
const lp=document.getElementById('locpad'),lb=document.getElementById('loc');let fly=false;

// true si un punto se ve en la pantalla
function onScreen(x,y){const q=P(x,y,0);return q[0]>40&&q[0]<W-40&&q[1]>90&&q[1]<H-90}
let lshow=null;setInterval(()=>{const show=cam.z<0.75;if(show!==lshow){lshow=show;lp.classList.toggle('off',!show)}
  if(fly&&me){fly=false;lp.classList.remove('wait');animTo({x:me.x,y:me.y,z:3})}},150);

// aviso corto arriba del mapa
function say(t){const n=document.getElementById('notice');n.hidden=false;n.textContent=t;clearTimeout(say.t);say.t=setTimeout(()=>updNotice(),2600)}
lb.onclick=()=>{
  if(me){const fuera=me.x<-150||me.x>S.w+150||me.y<-150||me.y>S.h+150;if(fuera){say('Estás fuera del campus.');return}animTo({x:me.x,y:me.y,z:3});return}
  if(!('geolocation' in navigator)||!window.isSecureContext){say('Este navegador no permite usar tu ubicación aquí.');return}
  if(gpsW===null)gpsBtn.click();fly=true;lp.classList.add('wait');say('Buscando tu ubicación…');
  setTimeout(()=>{if(fly&&!me){fly=false;lp.classList.remove('wait');const t=gpsInfo.textContent;say(t&&!/Buscando/.test(t)?t:'No se pudo obtener tu ubicación.')}},15000)};
// pedir la ubicación al abrir (como google maps); si no hay permiso, no molesta
try{if('geolocation' in navigator&&window.isSecureContext){const ok=()=>{if(gpsW===null)gpsBtn.click()};if(navigator.permissions&&navigator.permissions.query)navigator.permissions.query({name:'geolocation'}).then(p=>{if(p.state==='granted')ok()}).catch(()=>{});}}catch(e){}
// al tocar una sala: mover la cámara para verla completa sobre la hoja de abajo

// mueve la camara para ver la sala completa encima de la hoja
function frame(r){if(!r||!r.pts)return;const sh=document.getElementById('sheet');
  const c=Math.cos(cam.b),s=Math.sin(cam.b),cp=Math.max(.05,Math.cos(cam.p));const ce=centroid(r.pts);
  let x0=1e9,x1=-1e9,y0=1e9,y1=-1e9;r.pts.forEach(([x,y])=>{const dx=x-ce[0],dy=y-ce[1];const rx=dx*c-dy*s,ry=dx*s+dy*c;x0=Math.min(x0,rx);x1=Math.max(x1,rx);y0=Math.min(y0,ry);y1=Math.max(y1,ry)});
  const top=W<700?140:90,bot=H-(sh.offsetHeight||H*0.4)-16-(W>700?0:(document.getElementById('tabbar').offsetHeight||0)),vh=Math.max(120,bot-top),vw=W-(W<700?48:170);
  const zfit=Math.min(vw/Math.max(8,x1-x0),vh/Math.max(8,(y1-y0)*cp+20))*0.82;
  const zt=Math.max(ZMIN,Math.min(ZMAX,Math.min(zfit,Math.max(cam.z,2.6))));
  const ys=(top+bot)/2,ry=(ys-H*0.55)/(cp*zt);
  animTo({x:ce[0]-ry*s,y:ce[1]-ry*c,z:zt})}
const _or3=openRoom;openRoom=function(r){_or3(r);if(sel===r&&!reduceMotion())requestAnimationFrame(()=>frame(r));else if(sel===r)frame(r)};
})();


/* tocar pasillos, patios o fondos sin nombre no abre una hoja de "sala" */
(function(){const NO=['patio','pasillo','restringido','rampa','estacionamiento'];
const _o=openRoom;openRoom=function(r){if(r&&!r.label&&NO.includes(r.kind)){if(sel)closeSheet();return}_o(r)}})();


/* ===== secciones: mapa · reportes · mi perfil ===== */
(function(){
const B=document.body,tabs=[...document.querySelectorAll('#tabbar button')],pgRep=document.getElementById('pgRep'),pgPerf=document.getElementById('pgPerf');
let tab='map';B.dataset.tab='map';

// cambia entre las secciones mapa y reportes
function setTab(t){if(t===tab)return;tab=t;B.dataset.tab=t;
  tabs.forEach(b=>{if(b.dataset.tab===t)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current')});
  pgRep.hidden=t!=='rep';pgPerf.hidden=t!=='perf';cats.hidden=true;
  if(t==='rep')paintRep();if(t==='perf')paintPerf();if(t==='map')dirty=true;
  if(t!=='map'){closeSheet(true);closeReport()}}
window.setTab=setTab;
tabs.forEach(b=>b.onclick=()=>setTab(b.dataset.tab));
let rpE='act',rpCat=null;
const chips=document.getElementById('rpChips'),list=document.getElementById('rpList');

// filtro de la seccion reportes: activos, todos o mis apoyos
function pass(r){return rpE==='all'||(rpE==='act'&&r.e!=='resuelto')||(rpE==='mine'&&r.yo)}

// lista de la seccion reportes, ordenada por apoyos
function paintRep(){
  const base=REPORTS.filter(pass);
  document.getElementById('rpSub').textContent=`${REPORTS.filter(r=>r.e!=='resuelto').length} activos en el campus · ordenados por apoyos`;
  chips.innerHTML='';
  const mk=(id,html)=>{const b=document.createElement('button');b.type='button';b.setAttribute('aria-pressed',rpCat===id);b.innerHTML=html;if(!id)b.className='all';b.onclick=()=>{rpCat=id;paintRep()};chips.appendChild(b)};
  if(rpCat&&!base.some(r=>r.cat===rpCat))rpCat=null;
  mk(null,'Todos');
  CATS.forEach(c=>{const n=base.filter(r=>r.cat===c.id).length;if(n)mk(c.id,`<span class="ic" style="background:${c.c}">${svgIcon(c,15)}</span>${c.n} · ${n}`)});
  const L=base.filter(r=>!rpCat||r.cat===rpCat).sort((a,b)=>b.ap-a.ap);list.innerHTML='';
  if(!L.length){list.innerHTML=`<li class="empty">${rpE==='mine'?'Todavía no apoyas ningún reporte. Toca “A mí también me pasa” en uno.':'No hay reportes con este filtro.'}</li>`;return}
  L.forEach(r=>{const c=CAT[r.cat],li=document.createElement('li'),bt=document.createElement('button');bt.type='button';
    bt.innerHTML=`<span class="ic" style="background:${c.c}">${svgIcon(c,22)}</span><span class="tx"><b></b><small></small><span class="est ${r.e}">${ESTADO[r.e]}</span></span><span class="ap">▲ ${r.ap}<small>apoyos</small></span>`;
    bt.querySelector('b').textContent=r.t;bt.querySelector('.tx>small').textContent=lugar(r);
    bt.onclick=()=>{setTab('map');setTimeout(()=>goReport(r),60)};li.appendChild(bt);list.appendChild(li)})}
document.querySelectorAll('#pgRep .seg button').forEach(b=>b.onclick=()=>{rpE=b.dataset.e;document.querySelectorAll('#pgRep .seg button').forEach(x=>x.setAttribute('aria-pressed',x===b));paintRep()});
document.getElementById('rpCfg').onclick=e=>{e.stopPropagation();if(!cfgMode)cCfg.click();cats.hidden=!cats.hidden};
pgRep.addEventListener('pointerdown',e=>{if(!cats.hidden&&!e.target.closest('#rpCfg'))cats.hidden=true});
function paintPerf(){document.getElementById('pfAp').textContent=REPORTS.filter(r=>r.yo).length;document.getElementById('pfAct').textContent=REPORTS.filter(r=>r.e!=='resuelto').length}
document.getElementById('pfMine').onclick=()=>{setTab('rep');document.querySelector('#pgRep .seg [data-e="mine"]').click()};
document.querySelectorAll('#pgPerf .pdemo').forEach(b=>b.onclick=()=>{const n=document.getElementById('pfNote');n.hidden=false;clearTimeout(n._t);n._t=setTimeout(()=>n.hidden=true,2200)});
const tn=document.getElementById('tabN');const cnt=()=>{const n=REPORTS.filter(r=>r.e!=='resuelto').length;if(tn.textContent!==String(n))tn.textContent=n};cnt();setInterval(cnt,1000);
const lb=document.getElementById('loc');lb.addEventListener('click',()=>{lb.classList.remove('ping');void lb.offsetWidth;lb.classList.add('ping')});
})();


/* nombre completo de la sala (p. ej. b038 → laboratorio de programación avanzada) en la hoja y en la búsqueda */
(function(){
IDX.forEach(it=>{if(it.r.full)it.k=norm(it.r.label+' '+it.r.full)});
const _o=openRoom;openRoom=function(r){_o(r);if(sel===r&&r.full){const m=/^([A-Z]\d+)\s+(.*)$/.exec(r.label||'');
  document.getElementById('sTitle').textContent=m?'Sala '+m[1]+' · '+m[2]:r.label;
  document.getElementById('sSub').textContent=r.full+' · '+(r.building?r.building+' · ':'')+'Piso '+floor}};
})();


/* borde amarillo del edificio seleccionado al ver un piso (para no perder la selección) */
let OL={k:null,t:0};
function selOutline(){repPin();return;const k=selB+'|'+floor,now=performance.now();if(k!==OL.k){OL={k,t:now}}
  const a=reduceMotion()?1:Math.min(1,(now-OL.t)/320);if(a<1)dirty=true;
  S.buildings.forEach(b=>{if(b.name!==selB||b.bridge)return;const fp=(b.fp&&b.fp[floor])||b.pts;const q=fp.map(p=>P(p[0],p[1],5));
    ctx.save();ctx.globalAlpha=a*(typeof LA==='number'?LA:1);ctx.beginPath();q.forEach((p,i)=>i?ctx.lineTo(p[0],p[1]):ctx.moveTo(p[0],p[1]));ctx.closePath();
    ctx.fillStyle='rgba(255,199,44,.05)';ctx.fill();
    ctx.lineJoin='round';ctx.strokeStyle='rgba(255,199,44,.16)';ctx.lineWidth=8;ctx.stroke();
    ctx.strokeStyle='rgba(245,190,40,.55)';ctx.lineWidth=2.4;ctx.stroke();ctx.restore()})}


/* ===== lugares exteriores: canchas, estacionamientos, zonas de seguridad (se pueden tocar, buscar y reportar) ===== */
const R4=(x0,y0,x1,y1)=>[[x0,y0],[x1,y0],[x1,y1],[x0,y1]];
const EXT_PLACES=[
  {label:'Canchas de fútbol',pts:R4(400,325,700,635)},
  {label:'Multicancha',pts:R4(748,280,880,353)},
  {label:'Vóley playa',pts:R4(700,398,778,530)},
  {label:'Básquetbol',pts:R4(703,535,778,612)},
  {label:'Auditorio al aire libre',pts:R4(102,895,215,995)},
  ...(S.zones||[]).filter(z=>z.pts&&z.pts.length>2&&!z.dentro).map(z=>({label:z.t==='parking'?(z.n||'Estacionamiento'):z.n,pts:z.pts}))
].map(o=>Object.assign(o,{kind:'exterior',ext:true,building:''}));

// lugar exterior (cancha, estacionamiento) bajo el punto tocado
function placeAt(pt){let best=null,ba=1e18;EXT_PLACES.forEach(o=>{const q=o.pts.map(p=>P(p[0],p[1],0));if(inPoly(pt,q)){const a=Math.abs(area(o.pts));if(a<ba){ba=a;best=o}}});return best}
EXT_PLACES.forEach(r=>IDX.push({f:'ext',i:-1,r,k:norm(r.label)}));
function extSel(){if(floor!=='ext'||!sel||!sel.ext)return;const q=sel.pts.map(p=>P(p[0],p[1],0));
  ctx.save();ctx.beginPath();q.forEach((p,i)=>i?ctx.lineTo(p[0],p[1]):ctx.moveTo(p[0],p[1]));ctx.closePath();
  ctx.fillStyle='rgba(255,199,44,.28)';ctx.fill();ctx.lineJoin='round';ctx.strokeStyle='rgba(242,183,5,.9)';ctx.lineWidth=3;ctx.stroke();ctx.restore()}
(function(){
const _o=openRoom;openRoom=function(r){_o(r);if(sel===r&&r.ext){const zi=(S.zones||[]).find(z=>z.dentro===r.label);document.getElementById('sTitle').textContent=r.label;document.getElementById('sSub').textContent='Exterior del campus'+(zi?' · también '+zi.n:'');dirty=true}};
const _sf=setFloor;setFloor=function(f){if(sel&&sel.ext&&f!=='ext')sel=null;_sf(f)};
// botón reportar: si ya hay una sala o lugar abierto, reporta ahí al tiro
const fab=document.getElementById('fab'),tx=document.getElementById('pickTx'),pick=document.getElementById('pick');
fab.addEventListener('click',e=>{if(fab.getAttribute('aria-pressed')!=='true'&&sel&&document.getElementById('sheet').classList.contains('open')){e.stopImmediatePropagation();document.getElementById('sReport').click()}},true);
const msg=()=>{tx.textContent=floor==='ext'?'Toca el edificio o el lugar del problema (canchas, estacionamientos…)':'Toca la sala donde está el problema'};
new MutationObserver(()=>{if(!pick.hidden)msg()}).observe(pick,{attributes:true,attributeFilter:['hidden']});
const _sf2=setFloor;setFloor=function(f){_sf2(f);if(!pick.hidden)msg()};
// en modo reportar, tocar un edificio entra directo a su primer piso con salas
const _sb=selectBuilding;selectBuilding=function(n){_sb(n);if(n&&!pick.hidden&&floor==='ext'){const fl=(BFLOORS[n]||[]).filter(f=>f!=='ext');const f=fl.includes('1')?'1':fl[0];if(f)setFloor(f)}};
})();


/* ===== reportar: tocar en cualquier parte del mapa ===== */
let RPIN=null;

// pin amarillo del nuevo reporte: cae con rebote y deja una onda
function repPin(){if(!RPIN||RPIN.f!==floor)return;const q=P(RPIN.x,RPIN.y,floor==='ext'?0:5),el=performance.now()-RPIN.t,rm=reduceMotion();
  const t1=rm?1:Math.min(1,el/480),drop=rm?0:(()=>{const c1=1.70158*1.15,c3=c1+1,x=t1-1;return 1-(1+c3*x*x*x+c1*x*x)})();
  const t2=rm?1:Math.min(1,Math.max(0,(el-260)/900));if(t1<1||t2<1)dirty=true;
  const x=q[0],gy=q[1],hy=gy-drop*28,cy=hy-30,s=Math.min(1,0.4+t1*1.2);
  ctx.save();
  if(t2>0&&t2<1){ctx.globalAlpha=(1-t2)*.55;ctx.strokeStyle='#FFC72C';ctx.lineWidth=2;ctx.beginPath();ctx.ellipse(x,gy,8+t2*26,(8+t2*26)*.42,0,0,7);ctx.stroke()}
  ctx.globalAlpha=Math.min(1,t1*2);
  ctx.fillStyle='rgba(30,20,0,.22)';ctx.beginPath();ctx.ellipse(x,gy,7*s,2.8*s,0,0,7);ctx.fill();
  ctx.translate(x,hy);ctx.scale(s,s);
  ctx.shadowColor='rgba(60,40,0,.28)';ctx.shadowBlur=10;ctx.shadowOffsetY=4;
  ctx.fillStyle='#fff';ctx.beginPath();ctx.moveTo(0,0);ctx.lineTo(-6,-15);ctx.arc(0,-30,16,Math.PI*0.68,Math.PI*2.32);ctx.closePath();ctx.fill();
  ctx.shadowColor='transparent';
  ctx.fillStyle='#FFC72C';ctx.beginPath();ctx.arc(0,-30,12.5,0,7);ctx.fill();
  ctx.fillStyle='#2B2100';ctx.beginPath();ctx.moveTo(-5.5,-30);ctx.lineTo(5.5,-30);ctx.moveTo(0,-35.5);ctx.lineTo(0,-24.5);ctx.lineWidth=3;ctx.lineCap='round';ctx.strokeStyle='#2B2100';ctx.stroke();
  ctx.restore()}
(function(){
const pick=document.getElementById('pick'),tx=document.getElementById('pickTx'),sheet=document.getElementById('sheet');
const picking=()=>!pick.hidden;
const msg=()=>{tx.textContent=floor==='ext'?'Toca donde está el problema (o un edificio para entrar)':'Toca donde está el problema'};
new MutationObserver(()=>{if(picking())msg()}).observe(pick,{attributes:true,attributeFilter:['hidden']});

// sala o lugar mas cercano a un punto (para decir "cerca de ...")
function nearest(pt,list){let best=null,bd=1e9;list.forEach(r=>{const c=centroid(r.pts),d=Math.hypot(c[0]-pt[0],c[1]-pt[1]);if(d<bd){bd=d;best=r}});return [best,bd]}

// marca un punto con el pin y abre "nuevo reporte"
function point(mp,where,sub){RPIN={x:mp[0],y:mp[1],f:floor,t:performance.now()};sel=null;rebuild();
  document.getElementById('pickX').click();
  document.getElementById('sTitle').textContent='Nuevo reporte';document.getElementById('sSub').textContent=where+(sub?' · '+sub:'');
  sheet.classList.add('open');document.getElementById('sDemo').hidden=false;animTo({x:mp[0],y:mp[1],z:Math.max(cam.z,floor==='ext'?1.4:2.4)});dirty=true}
const _tap=tap;tap=function(e){
  if(!picking()){if(RPIN){RPIN=null;dirty=true}return _tap(e)}
  const r=cv.getBoundingClientRect(),pt=[e.clientX-r.left,e.clientY-r.top],mp=inv(pt[0],pt[1]);
  if(floor==='ext'){const b=buildingAt(pt);if(b){selectBuilding(b.name);return}
    const pl=placeAt(pt);if(pl){openRoom(pl);return}
    const [n,d]=nearest(mp,[...EXT_PLACES,...S.buildings.filter(b=>!b.bridge&&b.name.startsWith('Edificio')).map(b=>({label:b.name,pts:b.pts}))]);
    point(mp,'Exterior del campus',n&&d<160?'cerca de '+n.label:'');return}
  const h=pickRoom(pt);if(h&&h.label){openRoom(h);return}
  const rooms=(FLOORS_DATA[floor]||[]).filter(x=>x.label&&!/escalera|ascensor/i.test(x.label)&&(!selB||x.building===selB));
  const [n,d]=nearest(mp,rooms);
  if(n&&d<90)point(mp,'Cerca de '+(/^[A-Z]+\d/.test(n.label)?'sala '+n.label:n.label),(n.building||'')+' · Piso '+floor.replace('-','−'));
  else point(mp,'Pasillo o espacio común',[edificioEn(mp,floor)||selB,'Piso '+floor.replace('-','−')].filter(Boolean).join(' · '));
};
const _cs=closeSheet;closeSheet=function(k){if(RPIN){RPIN=null;dirty=true}_cs(k)};
})();


/* al cambiar de edificio estando en un piso: ir al piso con plano más cercano de ese edificio */
(function(){const ORD=FLOORS.filter(f=>f!=='ext');
const _sb=selectBuilding;selectBuilding=function(n){_sb(n);if(!n||floor==='ext')return;
  const fl=ORD.filter(f=>(FLOORS_DATA[f]||[]).some(r=>r.building===n&&r.label));if(!fl.length||fl.includes(floor))return;
  const i=ORD.indexOf(floor),hi=ORD.indexOf(fl[0]),lo=ORD.indexOf(fl[fl.length-1]);setFloor(i<hi?fl[0]:i>lo?fl[fl.length-1]:fl.reduce((a,f)=>Math.abs(ORD.indexOf(f)-i)<Math.abs(ORD.indexOf(a)-i)?f:a))}})();



/* ===== conexión con la app: reportar, apoyar, perfil y abrir un reporte por enlace ===== */
(function(){
// token de seguridad: se lee de la cookie al momento de apoyar (si la pagina quedo vieja, el de la pagina ya no sirve)
function csrf(){const m=document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);return m?decodeURIComponent(m[1]):UPIN.csrf}
function irA(url,params){const u=new URL(url,location.origin);Object.entries(params||{}).forEach(([k,v])=>{if(v!==undefined&&v!==null&&v!=='')u.searchParams.set(k,v)});location.href=u.toString()}
// "reportar aquí": sala real, lugar exterior o punto marcado con el pin
document.getElementById('sReport').onclick=()=>{
  if(sel&&sel.pk){irA(UPIN.urlCrear,{sala:sel.pk});return}
  if(sel&&sel.ext){const c=centroid(sel.pts);irA(UPIN.urlCrear,{piso:'ext',x:Math.round(c[0]),y:Math.round(c[1]),lugar:sel.label+' · Exterior del campus'});return}
  if(RPIN){const t=document.getElementById('sSub').textContent;irA(UPIN.urlCrear,{piso:RPIN.f,x:Math.round(RPIN.x),y:Math.round(RPIN.y),lugar:t});return}
  irA(UPIN.urlCrear)};
// apoyos guardados de verdad
const ap=document.getElementById('rApoyo');
function pintarApoyo(){if(!selRep)return;ap.textContent=selRep.yo?'Ya lo apoyaste · quitar':'A mí también me pasa';ap.classList.toggle('pri',!selRep.yo);ap.classList.toggle('sec',!!selRep.yo);
  const v=document.getElementById('rVer');if(v)v.href=selRep.url;
  const a=document.querySelector('#rTags .apo');if(a)a.textContent='▲ '+selRep.ap+(selRep.ap===1?' apoyo':' apoyos')}
const _or=openReport;openReport=function(r){_or(r);pintarApoyo()};
ap.onclick=async()=>{if(!selRep)return;ap.disabled=true;
  try{const res=await fetch(selRep.urlApoyo,{method:'POST',headers:{'X-CSRFToken':csrf(),'X-Requested-With':'fetch'},credentials:'same-origin'});
    if(!res.ok||!(res.headers.get('content-type')||'').includes('json')){location.reload();return}
    {const d=await res.json();selRep.ap=d.apoyos;selRep.yo=d.yo;openReport(selRep);ap.classList.remove('pop');void ap.offsetWidth;ap.classList.add('pop');dirty=true}}
  catch(e){location.reload();return}ap.disabled=false};
// mi perfil es la página de perfil de la app
const tp=document.querySelector('#tabbar [data-tab="perf"]');
if(tp)tp.addEventListener('click',e=>{e.stopImmediatePropagation();tp.classList.add('yendo');location.href=UPIN.urlPerfil},true);
// al volver con el boton atras el navegador puede mostrar la pagina guardada: se quita la marca de "yendo"
addEventListener('pageshow',()=>{if(tp)tp.classList.remove('yendo')});
// abrir un reporte que viene en el enlace (?reporte=12)
const q=new URLSearchParams(location.search).get('reporte');
if(q){const r=REPORTS.find(x=>String(x.pk)===q);if(r)setTimeout(()=>goReport(r),400)}
// abrir una sala que viene en el enlace (?sala=34)
const qs=new URLSearchParams(location.search).get('sala');
if(qs){for(const [f,rs] of Object.entries(FLOORS_DATA)){const r=rs.find(o=>String(o.pk)===qs);if(r){selectBuilding(r.building);setFloor(f);setTimeout(()=>{openRoom(r);const c=centroid(r.pts);animTo({x:c[0],y:c[1],z:2.6})},300);break}}}
})();
// "nuevo reporte" en un punto: sin las etiquetas de la última sala abierta
(function(){const t=document.getElementById('sTitle');
new MutationObserver(()=>{const m=document.querySelector('#sheet .meta');if(m)m.style.display=t.textContent==='Nuevo reporte'?'none':''}).observe(t,{childList:true,characterData:true,subtree:true})})();
// burbujita en el selector de pisos: cuantos reportes hay en cada piso (del edificio elegido y con los filtros puestos)
(function(){
function nPiso(f){return REPORTS.filter(r=>r.f===f&&(r.r||r.x!=null)&&(!selB||r.b===selB)&&repVisible(r)).length}
function burbujas(){FLOORS.forEach((f,i)=>{const b=nav.children[i];if(!b||f==='ext')return;
  const n=nPiso(f);let i_=b.querySelector('.fb');
  if(!n){if(i_)i_.remove();b.setAttribute('aria-label','Piso '+f);return}
  if(!i_){i_=document.createElement('i');i_.className='fb';i_.setAttribute('aria-hidden','true');b.appendChild(i_)}
  i_.textContent=n>9?'9+':n;b.setAttribute('aria-label','Piso '+f+', '+n+(n===1?' reporte':' reportes'))})}
const _pf=paintFloors;paintFloors=function(){_pf();burbujas()};
const _pc=paintCats;paintCats=function(){_pc();burbujas()};
burbujas()})();
// precarga mi perfil y la lista de reportes mientras se usa el mapa: al tocarlos se abren casi al instante
(function(){if(!HTMLScriptElement.supports||!HTMLScriptElement.supports('speculationrules'))return;
const s=document.createElement('script');s.type='speculationrules';
s.textContent=JSON.stringify({prerender:[{urls:[UPIN.urlPerfil],eagerness:'immediate'}],prefetch:[{urls:[UPIN.urlPerfil,UPIN.urlCrear]}]});document.head.appendChild(s)})();
// tutorial de bienvenida: la primera vez que se abre el mapa explica cada boton y los gestos del dispositivo.
// se puede ver de nuevo desde mi perfil (?tutorial=1)
(function(){
const CLAVE='upin_tutorial_v1';
const params=new URLSearchParams(location.search);
function visto(){try{return localStorage.getItem(CLAVE)==='1'}catch(e){return false}}
function marcar(){try{localStorage.setItem(CLAVE,'1')}catch(e){}}
const forzar=params.get('tutorial')==='1';
// si viene a ver un reporte o una sala por enlace, el tutorial espera a la proxima vez
if(!forzar&&(visto()||params.get('reporte')||params.get('sala')))return;

// que dispositivo es: tactil (celular o tablet) o computador con mouse/trackpad
const tactil=matchMedia('(pointer: coarse)').matches&&!matchMedia('(pointer: fine)').matches;
const celular=tactil&&Math.min(screen.width,screen.height)<600;
const equipo=tactil?(celular?'celular':'tablet'):'computador';

const ico={
  mover:'<path d="M12 3v18M3 12h18M12 3l-3 3M12 3l3 3M12 21l-3-3M12 21l3-3M3 12l3-3M3 12l3 3M21 12l-3-3M21 12l-3 3"/>',
  zoom:'<circle cx="10.5" cy="10.5" r="6.5"/><path d="M15.5 15.5L21 21M10.5 7.5v6M7.5 10.5h6"/>',
  girar:'<path d="M20 12a8 8 0 1 1-2.3-5.7"/><path d="M20 4v5h-5"/>',
  inclinar:'<path d="M4 17l8-4 8 4M4 11l8-4 8 4"/>',
  doble:'<circle cx="12" cy="12" r="3"/><circle cx="12" cy="12" r="7.5" stroke-dasharray="3 3"/>',
  botones:'<rect x="4" y="4" width="16" height="16" rx="4"/><path d="M9 12h6M12 9v6"/>'
};
const gestos=tactil?[
  ['mover','<b>Un dedo:</b> arrastra para moverte por el campus.'],
  ['zoom','<b>Pellizca</b> con dos dedos para acercar o alejar.'],
  ['girar','<b>Gira dos dedos</b> para rotar el mapa.'],
  ['inclinar','<b>Desliza dos dedos</b> hacia arriba o abajo para inclinar la vista.'],
  ['doble','<b>Doble toque</b> para acercarte a un punto.']
]:[
  ['mover','<b>Arrastra</b> con el clic izquierdo para moverte.'],
  ['zoom','<b>Rueda del mouse</b> (o pellizco en el trackpad) para acercar o alejar.'],
  ['girar','<b>Clic derecho + arrastrar</b> (o Shift + arrastrar) para girar e inclinar.'],
  ['doble','<b>Doble clic</b> para acercarte a un punto.'],
  ['botones','También tienes los botones <b>+ −</b> y <b>⟲ ⟳</b> de la esquina.']
];
const vis=el=>{if(!el)return false;const r=el.getBoundingClientRect();const s=getComputedStyle(el);return r.width>0&&r.height>0&&s.visibility!=='hidden'&&s.display!=='none'};
const caja=sels=>{let r=null;sels.map(s=>document.querySelector(s)).filter(vis).forEach(el=>{const b=el.getBoundingClientRect();r=r?{left:Math.min(r.left,b.left),top:Math.min(r.top,b.top),right:Math.max(r.right,b.right),bottom:Math.max(r.bottom,b.bottom)}:{left:b.left,top:b.top,right:b.right,bottom:b.bottom}});return r};
const logo='<svg viewBox="-4 -14 72 78" width="64" height="70" aria-hidden="true"><path fill="#FFC72C" d="M32 4C19.3 4 9 14.3 9 27c0 15.6 23 33 23 33s23-17.4 23-33C55 14.3 44.7 4 32 4z"/><circle cx="24.5" cy="26" r="3.2" fill="#2B2100"/><circle cx="39.5" cy="26" r="3.2" fill="#2B2100"/><path fill="none" stroke="#2B2100" stroke-width="4.6" stroke-linecap="round" d="M23.5 33.5v1a8 8 0 0 0 17 0v-1"/><g transform="translate(32 3) scale(.72) rotate(-16) translate(-32 -10)"><path fill="#1D1D1F" d="M20 11v8c0 4 24 4 24 0v-8z"/><path fill="#1D1D1F" stroke="#fff" stroke-width="1.6" d="M32 -1L59 9 32 19 5 9z"/></g></svg>';
const toca=tactil?'Toca':'Haz clic en';
const PASOS=[
  {inicio:true,t:'Hola, esto es U-Pin',x:'Encuentra cualquier sala del campus, mira qué problemas hay y repórtalos en segundos. Te mostramos cómo usarlo en un minuto.',
   nota:'Estás en un <b>'+equipo+'</b>: al final te mostramos los gestos para '+(tactil?'tu pantalla táctil':'el mouse y el trackpad')+'.'},
  {t:'Edificios y salas',x:toca+' un edificio para ver sus salas y '+(tactil?'toca':'haz clic en')+' una sala para ver qué es y reportar algo ahí. Los pines amarillos dicen cuántos reportes hay en cada edificio.'},
  {s:['#floors','#fltog'],t:'Pisos',x:(document.getElementById('floors').classList.contains('fcol')&&tactil?toca+' aquí para abrir los pisos. ':'Cambia de piso aquí. ')+'La <b>burbujita negra</b> en un piso dice cuántos reportes hay en ese piso. <b>Ext</b> es el exterior del campus.'},
  {s:['.search'],t:'Buscar',x:'Escribe el nombre de una sala, oficina o lugar (por ejemplo <b>K303</b> o <b>Biblioteca</b>) y el mapa te lleva ahí.'},
  {s:['.mode'],t:'Vista 2D o 2.5D',x:'Cambia entre el plano visto desde arriba (2D) y los edificios en relieve (2.5D).'},
  {s:['#fab'],t:'Reportar',x:toca+' <b>Reportar</b> y después '+(tactil?'toca':'haz clic en')+' el lugar exacto del problema en el mapa. También puedes reportar desde cualquier sala.'},
  {s:['#tabbar'],t:'Mapa, reportes y perfil',x:'En <b>Reportes</b> ves los problemas del campus y los filtras por tipo. En <b>Mi perfil</b> están tus reportes y tu cuenta.'},
  {fin:true,t:'Gestos en tu '+equipo,x:'Así te mueves por el mapa:'}
].filter(p=>!p.s||caja(p.s));

let i=0,raiz,card,anillo,sombra;
function armar(){
  raiz=document.createElement('div');raiz.className='tuto';raiz.setAttribute('role','dialog');raiz.setAttribute('aria-modal','true');raiz.setAttribute('aria-labelledby','tutoT');
  raiz.innerHTML='<div class="tuto-bloq"></div><div class="tuto-s"></div><div class="tuto-anillo"></div><div class="tuto-card" tabindex="-1"></div>';
  document.body.appendChild(raiz);
  sombra=raiz.querySelector('.tuto-s');anillo=raiz.querySelector('.tuto-anillo');card=raiz.querySelector('.tuto-card');
  raiz.addEventListener('click',e=>{const b=e.target.closest('[data-a]');if(!b)return;const a=b.dataset.a;if(a==='sig')ir(i+1);else if(a==='atras')ir(i-1);else cerrar()});
  addEventListener('keydown',tecla,true);addEventListener('resize',ubicar);
  requestAnimationFrame(()=>raiz.classList.add('on'));
}
function tecla(e){if(!raiz)return;const k={Escape:cerrar,ArrowRight:()=>ir(i+1),ArrowLeft:()=>ir(i-1)}[e.key];if(k){e.preventDefault();e.stopImmediatePropagation();k()}}
function ir(n){if(n<0)return;if(n>=PASOS.length){cerrar();return}i=n;pintar()}
function pintar(){
  const p=PASOS[i],ult=i===PASOS.length-1;
  let h='';
  if(p.inicio)h+='<div class="tuto-logo">'+logo+'</div>';
  else h+='<div class="tuto-cab"><span class="tuto-puntos" aria-hidden="true">'+PASOS.slice(1).map((_,k)=>'<i'+(k+1===i?' class="on"':'')+'></i>').join('')+'</span><span class="tuto-paso">Paso '+i+' de '+(PASOS.length-1)+'</span></div>';
  h+='<h2 id="tutoT">'+p.t+'</h2><p>'+p.x+'</p>';
  if(p.nota)h+='<p class="tuto-nota">'+p.nota+'</p>';
  if(p.fin)h+='<ul class="tuto-gestos">'+gestos.map(([k,t])=>'<li><span class="tuto-ic"><svg viewBox="0 0 24 24" aria-hidden="true">'+ico[k]+'</svg></span><span>'+t+'</span></li>').join('')+'</ul>';
  h+='<div class="tuto-pie">';
  if(p.inicio)h+='<button type="button" class="tuto-saltar" data-a="saltar">Saltar</button><button type="button" class="tuto-pri" data-a="sig">Ver cómo funciona</button>';
  else{
    h+=(ult?'<span></span>':'<button type="button" class="tuto-saltar" data-a="saltar">Saltar</button>')+'<span class="tuto-btns"><button type="button" class="tuto-sec" data-a="atras" aria-label="Paso anterior">Atrás</button><button type="button" class="tuto-pri" data-a="sig">'+(ult?'Ir al mapa':'Siguiente')+'</button></span>';
  }
  h+='</div>';
  card.innerHTML=h;card.classList.toggle('grande',!!(p.inicio||p.fin));
  card.classList.remove('entra');void card.offsetWidth;card.classList.add('entra');
  ubicar();
  card.focus({preventScroll:true});
}
function ubicar(){
  if(!raiz)return;
  const p=PASOS[i],W=innerWidth,H=innerHeight,m=8;
  let r=p.s?caja(p.s):null;
  if(r)r={left:r.left-m,top:r.top-m,right:r.right+m,bottom:r.bottom+m};
  // una sola capa difuminada con un hueco redondeado recortado (sin hueco: el hueco mide cero en el centro)
  const hx=r?r.left:W/2,hy=r?r.top:H/2,hw=r?r.right-r.left:0,hh=r?r.bottom-r.top:0,ra=r?Math.min(22,hw/2,hh/2):0;
  const n=v=>Math.round(v*10)/10;
  sombra.style.clipPath=`path(evenodd,"M0 0H${W}V${H}H0Z M${n(hx+ra)} ${n(hy)}H${n(hx+hw-ra)}A${ra} ${ra} 0 0 1 ${n(hx+hw)} ${n(hy+ra)}V${n(hy+hh-ra)}A${ra} ${ra} 0 0 1 ${n(hx+hw-ra)} ${n(hy+hh)}H${n(hx+ra)}A${ra} ${ra} 0 0 1 ${n(hx)} ${n(hy+hh-ra)}V${n(hy+ra)}A${ra} ${ra} 0 0 1 ${n(hx+ra)} ${n(hy)}Z")`;
  const pon=(el,x,y,w,h)=>{el.style.left=x+'px';el.style.top=y+'px';el.style.width=Math.max(0,w)+'px';el.style.height=Math.max(0,h)+'px'};
  anillo.style.opacity=r?1:0;if(r)pon(anillo,hx,hy,hw,hh);
  // la tarjeta va al lado del hueco donde quepa (abajo, arriba, izquierda, derecha) o al centro
  const cw=card.offsetWidth,ch=card.offsetHeight,g=14,b=16;
  const clamp=(v,a,z)=>Math.max(a,Math.min(z,v));
  let x=(W-cw)/2,y=(H-ch)/2;
  if(r){const cx=(r.left+r.right)/2,cy=(r.top+r.bottom)/2;
    const op=[[cx-cw/2,r.bottom+g,r.bottom+g+ch<=H-b],[cx-cw/2,r.top-g-ch,r.top-g-ch>=b],[r.left-g-cw,cy-ch/2,r.left-g-cw>=b],[r.right+g,cy-ch/2,r.right+g+cw<=W-b]];
    const o=op.find(o=>o[2]);if(o){x=o[0];y=o[1]}}
  card.style.left=clamp(x,b,W-cw-b)+'px';card.style.top=clamp(y,b,H-ch-b)+'px';
}
function cerrar(){marcar();if(!raiz)return;removeEventListener('keydown',tecla,true);removeEventListener('resize',ubicar);
  const r=raiz;raiz=null;r.classList.remove('on');setTimeout(()=>r.remove(),320);
  if(forzar)history.replaceState(null,'',location.pathname)}
function empezar(){setTimeout(()=>{armar();pintar()},forzar?250:700)}
if(document.prerendering)document.addEventListener('prerenderingchange',empezar,{once:true});else empezar();
})();

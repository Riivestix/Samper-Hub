import os,json,base64,sqlite3,threading,time,uuid,mimetypes,hashlib,hmac,urllib.parse,urllib.request
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from datetime import datetime,timezone
P=int(os.getenv("PORT","8080")); D=os.getenv("DATA_DIR","/data"); U=D+"/uploads"; DB=D+"/db.sqlite"
BASE=os.getenv("PUBLIC_BASE_URL","").rstrip("/"); MT=os.getenv("MCP_TOKEN",""); AK=os.getenv("ADMIN_KEY",""); GV=os.getenv("META_GRAPH_VERSION","v24.0")
os.makedirs(U,exist_ok=True)
def con():
 c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;c.execute("create table if not exists kv(k text primary key,v text)");c.execute("create table if not exists q(id text primary key,due text,t text,p text,m text,s text,r text)");c.commit();return c
def g(k):
 with con() as c:
  r=c.execute("select v from kv where k=?",(k,)).fetchone();return r["v"] if r else ""
def sv(k,v):
 with con() as c:c.execute("insert into kv values(?,?) on conflict(k) do update set v=excluded.v",(k,v));c.commit()
def req(method,url,head={},data=None,form=None):
 h=dict(head)
 if form is not None:data=urllib.parse.urlencode(form).encode();h["Content-Type"]="application/x-www-form-urlencoded"
 elif data is not None:data=json.dumps(data).encode();h["Content-Type"]="application/json"
 try:
  with urllib.request.urlopen(urllib.request.Request(url,data=data,headers=h,method=method),timeout=90) as r:return r.status,json.loads(r.read().decode() or "{}")
 except urllib.error.HTTPError as e:
  try:o=json.loads(e.read().decode())
  except:o={"error":"HTTP "+str(e.code)}
  return e.code,o
def esc(s):return urllib.parse.quote(str(s),safe="~-._")
def oa(method,url,params={}):
 ck,cs,at,ats=[g(x) for x in ("x_ck","x_cs","x_at","x_as")]
 if not all((ck,cs,at,ats)):raise Exception("X noch nicht verbunden")
 o={"oauth_consumer_key":ck,"oauth_nonce":uuid.uuid4().hex,"oauth_signature_method":"HMAC-SHA1","oauth_timestamp":str(int(time.time())),"oauth_token":at,"oauth_version":"1.0"}
 a={**o,**params}; ps="&".join(f"{esc(k)}={esc(v)}" for k,v in sorted(a.items()));bs="&".join((method,esc(url.split("?")[0]),esc(ps)));key=f"{esc(cs)}&{esc(ats)}".encode();o["oauth_signature"]=base64.b64encode(hmac.new(key,bs.encode(),hashlib.sha1).digest()).decode()
 return "OAuth "+", ".join(f'{esc(k)}="{esc(v)}"' for k,v in sorted(o.items()))
def x(method,path,data=None,params={}):
 url="https://api.x.com"+path+("?"+urllib.parse.urlencode(params) if params else "");return req(method,url,{"Authorization":oa(method,url,params if method=="GET" else {})},data)
def xm(url):
 rr=urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"RIIVESTIX"}),timeout=60)
 b,ct=rr.read(),rr.headers.get_content_type() or mimetypes.guess_type(url)[0] or "image/jpeg"
 bd="----r"+uuid.uuid4().hex; body=(f"--{bd}\r\nContent-Disposition: form-data; name=\"media\"; filename=\"img\"\r\nContent-Type: {ct}\r\n\r\n").encode()+b+f"\r\n--{bd}--\r\n".encode()
 u="https://upload.twitter.com/1.1/media/upload.json";r=urllib.request.Request(u,data=body,headers={"Authorization":oa("POST",u),"Content-Type":f"multipart/form-data; boundary={bd}"},method="POST")
 with urllib.request.urlopen(r,timeout=120) as z:o=json.loads(z.read().decode());return str(o.get("media_id_string") or o["media_id"])
def px(t,m):
 d={"text":t}
 if m:d["media"]={"media_ids":[xm(u) for u in m[:4]]}
 s,o=x("POST","/2/tweets",d)
 if s>=300:raise Exception(json.dumps(o))
 return o
def dx(i):
 s,o=x("DELETE","/2/tweets/"+i)
 if s>=300:raise Exception(json.dumps(o))
 return o
def xme():
 s,o=x("GET","/2/users/me",params={"user.fields":"id,name,username,public_metrics"})
 if s>=300:raise Exception(json.dumps(o))
 return o.get("data",o)
def xl(n=10):
 me=xme();s,o=x("GET",f"/2/users/{me['id']}/tweets",params={"max_results":max(5,min(int(n),100)),"tweet.fields":"id,text,created_at,public_metrics"})
 if s>=300:raise Exception(json.dumps(o))
 return o.get("data",[])
def ig(method,path,form=None,fields=""):
 tok=g("ig_tok");uid=g("ig_uid")
 if not tok or not uid:raise Exception("Instagram noch nicht verbunden")
 if fields:return req("GET",f"https://graph.facebook.com/{GV}/{path}?"+urllib.parse.urlencode({"fields":fields,"access_token":tok}))
 f=dict(form or {});f["access_token"]=tok;return req(method,f"https://graph.facebook.com/{GV}/{path}",form=f)
def pig(t,m):
 if not m:raise Exception("Instagram benötigt mindestens ein Bild")
 uid=g("ig_uid")
 if len(m)==1:
  s,o=ig("POST",uid+"/media",{"image_url":m[0],"caption":t})
  if s>=300:raise Exception(json.dumps(o))
  s,o=ig("POST",uid+"/media_publish",{"creation_id":o["id"]});return o
 ids=[]
 for u in m[:10]:
  s,o=ig("POST",uid+"/media",{"image_url":u,"is_carousel_item":"true"})
  if s>=300:raise Exception(json.dumps(o))
  ids.append(o["id"])
 s,o=ig("POST",uid+"/media",{"media_type":"CAROUSEL","children":",".join(ids),"caption":t})
 if s>=300:raise Exception(json.dumps(o))
 s,o=ig("POST",uid+"/media_publish",{"creation_id":o["id"]});return o
def il(n=10):
 s,o=ig("GET",g("ig_uid")+"/media",fields="id,caption,media_type,media_url,permalink,timestamp,like_count,comments_count")
 if s>=300:raise Exception(json.dumps(o))
 return o.get("data",[])[:int(n)]
def ia():
 s,o=ig("GET",g("ig_uid"),fields="id,username,name,followers_count,follows_count,media_count")
 if s>=300:raise Exception(json.dumps(o))
 return o
def pub(t,p,m):
 r={}
 for a in p:
  try:r[a]={"ok":1,"data":pig(t,m) if a=="instagram" else px(t,m)}
  except Exception as e:r[a]={"ok":0,"error":str(e)}
 return r
def due(s):
 try:return datetime.fromisoformat(s.replace("Z","+00:00"))<=datetime.now(timezone.utc)
 except:return False
def sched():
 while 1:
  try:
   with con() as c:
    for r in c.execute("select * from q where s='pending'").fetchall():
     if due(r["due"]):
      z=pub(r["t"],json.loads(r["p"]),json.loads(r["m"]));c.execute("update q set s=?,r=? where id=?",("sent" if all(v["ok"] for v in z.values()) else "partial",json.dumps(z),r["id"]));c.commit()
  except:pass
  time.sleep(30)
TOOLS=[
{"name":"get_accounts","description":"Verbundene Accounts prüfen","inputSchema":{"type":"object","properties":{}}},
{"name":"upload_asset","description":"Bild als HTTPS-Datei speichern","inputSchema":{"type":"object","properties":{"filename":{"type":"string"},"data_base64":{"type":"string"}},"required":["filename","data_base64"]}},
{"name":"publish_post","description":"Auf Instagram/X veröffentlichen","inputSchema":{"type":"object","properties":{"text":{"type":"string"},"platforms":{"type":"array","items":{"type":"string","enum":["instagram","x"]}},"media_urls":{"type":"array","items":{"type":"string"}}},"required":["text","platforms"]}},
{"name":"schedule_post","description":"Post planen","inputSchema":{"type":"object","properties":{"text":{"type":"string"},"platforms":{"type":"array","items":{"type":"string","enum":["instagram","x"]}},"media_urls":{"type":"array","items":{"type":"string"}},"due_at":{"type":"string"}},"required":["text","platforms","due_at"]}},
{"name":"list_scheduled","description":"Planungen anzeigen","inputSchema":{"type":"object","properties":{}}},
{"name":"cancel_scheduled","description":"Planung stornieren","inputSchema":{"type":"object","properties":{"id":{"type":"string"}},"required":["id"]}},
{"name":"list_posts","description":"Posts abrufen","inputSchema":{"type":"object","properties":{"platform":{"type":"string","enum":["instagram","x"]},"limit":{"type":"integer"}},"required":["platform"]}},
{"name":"delete_post","description":"X-Post löschen; Instagram-Löschen ist offiziell nicht verfügbar","inputSchema":{"type":"object","properties":{"platform":{"type":"string","enum":["instagram","x"]},"post_id":{"type":"string"}},"required":["platform","post_id"]}},
{"name":"get_analytics","description":"Kennzahlen abrufen","inputSchema":{"type":"object","properties":{"platform":{"type":"string","enum":["instagram","x"]}},"required":["platform"]}}]
def call(n,a):
 if n=="get_accounts":
  r={"instagram":{"configured":bool(g("ig_tok") and g("ig_uid"))},"x":{"configured":bool(g("x_ck") and g("x_cs") and g("x_at") and g("x_as"))}}
  if r["instagram"]["configured"]:
   try:r["instagram"]["profile"]=ia()
   except Exception as e:r["instagram"]["error"]=str(e)
  if r["x"]["configured"]:
   try:r["x"]["profile"]=xme()
   except Exception as e:r["x"]["error"]=str(e)
  return r
 if n=="upload_asset":
  raw=base64.b64decode(a["data_base64"].split(",")[-1]);fn=uuid.uuid4().hex+"_"+"".join(c for c in a["filename"] if c.isalnum() or c in "._-");open(U+"/"+fn,"wb").write(raw);return {"url":BASE+"/media/"+urllib.parse.quote(fn)}
 if n=="publish_post":return pub(a["text"],a["platforms"],a.get("media_urls",[]))
 if n=="schedule_post":
  i=uuid.uuid4().hex
  with con() as c:c.execute("insert into q values(?,?,?,?,?,'pending','')",(i,a["due_at"],a["text"],json.dumps(a["platforms"]),json.dumps(a.get("media_urls",[]))));c.commit()
  return {"id":i,"due_at":a["due_at"]}
 if n=="list_scheduled":
  with con() as c:return [dict(x) for x in c.execute("select * from q order by due").fetchall()]
 if n=="cancel_scheduled":
  with con() as c:z=c.execute("update q set s='cancelled' where id=? and s='pending'",(a["id"],));c.commit();return {"cancelled":z.rowcount==1}
 if n=="list_posts":return il(a.get("limit",10)) if a["platform"]=="instagram" else xl(a.get("limit",10))
 if n=="delete_post":return {"unsupported":1,"reason":"Instagram API unterstützt kein allgemeines Löschen veröffentlichter Feed-Posts"} if a["platform"]=="instagram" else dx(a["post_id"])
 if n=="get_analytics":return ia() if a["platform"]=="instagram" else {"profile":xme(),"recent_posts":xl(10)}
 raise Exception("unknown tool")
def jr(h,s,o):
 b=json.dumps(o,ensure_ascii=False).encode();h.send_response(s);h.send_header("Content-Type","application/json");h.send_header("Content-Length",str(len(b)));h.send_header("Access-Control-Allow-Origin","*");h.end_headers();h.wfile.write(b)
class H(BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def do_OPTIONS(self):
  self.send_response(204);self.send_header("Access-Control-Allow-Origin","*");self.send_header("Access-Control-Allow-Headers","content-type,authorization,mcp-session-id");self.send_header("Access-Control-Allow-Methods","GET,POST,OPTIONS");self.end_headers()
 def do_GET(self):
  p=urllib.parse.urlparse(self.path).path
  if p in ("/","/health"):return jr(self,200,{"ok":1,"service":"RIIVESTIX Social"})
  if p.startswith("/media/"):
   f=urllib.parse.unquote(p[7:])
   if "/" in f or ".." in f or not os.path.isfile(U+"/"+f):return jr(self,404,{"error":"not found"})
   b=open(U+"/"+f,"rb").read();self.send_response(200);self.send_header("Content-Type",mimetypes.guess_type(f)[0] or "application/octet-stream");self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b);return
  if p=="/setup/"+AK:
   h=f"""<meta name=viewport content='width=device-width'><body style='font-family:system-ui;max-width:700px;margin:40px auto;background:#111;color:#eee'><h1>RIIVESTIX Social</h1><p>Einmal Zugangsdaten eintragen. Danach übernimmt ChatGPT.</p><form method=post><h2>Instagram</h2><input name=ig_uid placeholder='IG User ID' style='width:100%;padding:10px'><br><input type=password name=ig_tok placeholder='Access Token' style='width:100%;padding:10px'><h2>X</h2><input name=x_ck placeholder='API Key' style='width:100%;padding:10px'><br><input type=password name=x_cs placeholder='API Secret' style='width:100%;padding:10px'><br><input name=x_at placeholder='Access Token' style='width:100%;padding:10px'><br><input type=password name=x_as placeholder='Access Token Secret' style='width:100%;padding:10px'><p><button>Speichern</button></p></form><p>Connector: <code>{BASE}/mcp/{MT}</code></p></body>""";b=h.encode();self.send_response(200);self.send_header("Content-Type","text/html; charset=utf-8");self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b);return
  if p=="/mcp/"+MT:return jr(self,405,{"error":"use POST"})
  return jr(self,404,{"error":"not found"})
 def do_POST(self):
  p=urllib.parse.urlparse(self.path).path;n=int(self.headers.get("Content-Length","0"));raw=self.rfile.read(n)
  if p=="/setup/"+AK:
   f=urllib.parse.parse_qs(raw.decode())
   for k in ("ig_uid","ig_tok","x_ck","x_cs","x_at","x_as"):
    if f.get(k):sv(k,f[k][0].strip())
   b="<h2>Gespeichert ✓</h2><p>Fenster kann geschlossen werden.</p>".encode();self.send_response(200);self.send_header("Content-Type","text/html; charset=utf-8");self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b);return
  if p!="/mcp/"+MT:return jr(self,404,{"error":"not found"})
  try:q=json.loads(raw or b"{}")
  except:return jr(self,400,{"error":"bad json"})
  m=q.get("method");i=q.get("id")
  if m=="initialize":return jr(self,200,{"jsonrpc":"2.0","id":i,"result":{"protocolVersion":(q.get("params") or {}).get("protocolVersion","2025-06-18"),"capabilities":{"tools":{}},"serverInfo":{"name":"RIIVESTIX Social","version":"1.0"}}})
  if m=="tools/list":return jr(self,200,{"jsonrpc":"2.0","id":i,"result":{"tools":TOOLS}})
  if m=="tools/call":
   try:o=call((q.get("params") or {})["name"],(q.get("params") or {}).get("arguments",{}));r={"content":[{"type":"text","text":json.dumps(o,ensure_ascii=False)}]}
   except Exception as e:r={"content":[{"type":"text","text":str(e)}],"isError":True}
   return jr(self,200,{"jsonrpc":"2.0","id":i,"result":r})
  if m=="notifications/initialized":self.send_response(202);self.end_headers();return
  return jr(self,200,{"jsonrpc":"2.0","id":i,"result":{}})
threading.Thread(target=sched,daemon=True).start();ThreadingHTTPServer(("0.0.0.0",P),H).serve_forever()

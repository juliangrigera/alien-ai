import os, base64, json, csv
from pathlib import Path
from dotenv import load_dotenv
from tqdm import tqdm
from openai import OpenAI
from PIL import Image

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ---- Config ----
MODEL = "gpt-4o"   # or whatever you want to use
INPUT_DIR = Path("screenshots_1/batch00_test")
OUT_CSV = Path("ratings.csv")

SYSTEM_PROMPT = """You are a strict UI rater.

Rate screenshots on three 1–10 integer scales:

1. Aesthetic — visual quality based on layout, color, typography, and polish. 
	Avoid high scores for flat or noisy designs.
2. Level of Detail — richness and structure of components, organization. 
	Be forgiving with sparse drafts; lightly penalize repetition.
3. Utility for Designers — usefulness for design inspiration, based on 
	aesthetic+detail but adjusted for clarity and layout richness.
4. Orderliness — how orderly the UI appears.
5. Complexity - how visually complex the UI appears in the screenshot
6. Overall - rate the website design on a 10 point scale
	
Return ONLY a compact JSON object with integer scores 1–10:
{
	"aesthetic": <int 1-10>,
	"detail": <int 1-10>,	
	"utility_for_designer": <int 1-10>,
	"orderliness": <int 1-10>,
	"complexity": <int 1-10>,
	"overall": <int 1-10>,
	"notes": "<one short sentence>"
}
"""

def img_to_data_uri(path: Path) -> str:
	 with Image.open(path) as im:
		  im = im.convert("RGB")
		  if max(im.size) > 1600:
		  	im.thumbnail((1600, 1600))
		  buf = Path("_tmp.jpg")
		  im.save(buf, format="JPEG", quality=90)
		  b64 = base64.b64encode(buf.read_bytes()).decode("utf-8")
		  buf.unlink(missing_ok=True)
	 return f"data:image/jpeg;base64,{b64}"

def rate_image(path: Path) -> dict:
	 data_uri = img_to_data_uri(path)
	 msg = [
		  {"role": "system", "content": SYSTEM_PROMPT},
		  {
				"role": "user",
				"content": [
					 {"type": "text", "text": "Rate this UI screenshot."},
					 {"type": "image_url", "image_url": {"url": data_uri}}
				]
		  }
	 ]
	 resp = client.chat.completions.create(
		  model=MODEL,
		  messages=msg,
		  temperature=0,
		  top_p=1,    
		  seed=42,
		  response_format={"type": "json_object"} 		
	 )
	 raw = resp.choices[0].message.content.strip()
	 raw = raw.strip("`").replace("json\n", "").replace("JSON\n", "")
	 return json.loads(raw)

def main():
	images = sorted([
		p for p in INPUT_DIR.iterdir()
		if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
	])
	if not images:
		print(f"No images in {INPUT_DIR}")
		return

	COLUMNS = ["file", "aesthetic", "detail", "utility_for_designer", "notes", "error"]

	rows = []
	for p in tqdm(images, desc="Rating"):
		try:
			r = rate_image(p)
			rows.append({
				"file": p.name,
				"aesthetic": r.get("aesthetic"),
				"detail": r.get("detail"),
				"utility_for_designer": r.get("utility_for_designer"),
				"notes": r.get("notes", ""),
				"error": ""  # ensure column exists
			})
		except Exception as e:
			  rows.append({
					"file": p.name,
					"aesthetic": "",
					"detail": "",
					"utility_for_designer": "",
					"notes": "",
					"error": str(e)
			  })

	with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
		w = csv.DictWriter(f, fieldnames=COLUMNS)
		w.writeheader()
		w.writerows(rows)
	
	print(f"Wrote {OUT_CSV}")

if __name__ == "__main__":
	 main()

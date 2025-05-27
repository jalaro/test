from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import json

app = FastAPI()

# 載入內建斷層資料
with open("fault_data.json", "r", encoding="utf-8") as f:
    fault_db = json.load(f)

# 啟用 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/get_seismic_coefficients")
def get_seismic_coefficients(fault_name: str = Query(...), distance_km: float = Query(...), location: str = Query(None)):
    fault = fault_db.get(fault_name)
    if not fault:
        return {"error": "斷層名稱未找到"}

    # 取出所有距離點，轉為 float
    distances = sorted(float(d) for d in fault.keys())
    r = distance_km

    # 找最接近的兩點
    r1, r2 = None, None
    for i in range(len(distances) - 1):
        if distances[i] <= r <= distances[i + 1]:
            r1 = distances[i]
            r2 = distances[i + 1]
            break

    if r1 is None or r2 is None:
        return {"error": f"距離 {r} 不在有效範圍 {distances[0]} ~ {distances[-1]} 之間"}

    def interp(val1, val2):
        return round(val1 + (r - r1) * (val2 - val1) / (r2 - r1), 3)

    v1 = fault[str(int(r1))]
    v2 = fault[str(int(r2))]

    result = {
        "fault_name": fault_name,
        "location": location,
        "distance_km": r,
        "SDS": interp(v1["SDS"], v2["SDS"]),
        "SD1": interp(v1["SD1"], v2["SD1"]),
        "SMS": interp(v1["SMS"], v2["SMS"]),
        "SM1": interp(v1["SM1"], v2["SM1"]),
    }

    return result

if __name__ == "__main__":
    uvicorn.run("get_seismic_coefficients:app", host="0.0.0.0", port=8000, reload=True)
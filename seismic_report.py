from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import json

app = FastAPI()

with open("fault_data.json", "r", encoding="utf-8") as f:
    fault_db = json.load(f)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def linear_interp(r, r1, r2, v1, v2):
    return round(v1 + (r - r1) * (v2 - v1) / (r2 - r1), 3)

def calculate_fu(R, T_T0):
    if T_T0 <= 0.2:
        return R
    elif T_T0 <= 0.6:
        return round(R - (R - 1) * (T_T0 - 0.2) / 0.4, 3)
    elif T_T0 <= 1.0:
        return round(1 + (R - 1) * (1 - T_T0) / 0.4, 3)
    else:
        return 1.0

@app.get("/seismic_report")
def seismic_report(
    fault_name: str = Query(...),
    distance_km: float = Query(...),
    T: float = Query(...),
    R: float = Query(...),
    I: float = Query(...),
    alpha_y: float = Query(...),
    W: float = Query(...),
    location: str = Query(None)
):
    fault = fault_db.get(fault_name)
    if not fault:
        return {"error": "找不到指定的斷層資料"}

    r = distance_km
    distances = sorted(float(d) for d in fault.keys())
    r1, r2 = None, None
    for i in range(len(distances) - 1):
        if distances[i] <= r <= distances[i + 1]:
            r1 = distances[i]
            r2 = distances[i + 1]
            break
    if r1 is None or r2 is None:
        return {"error": f"距離 {r} 超出支援範圍：{distances}"}

    v1 = fault[str(int(r1))]
    v2 = fault[str(int(r2))]

    SDS = linear_interp(r, r1, r2, v1["SDS"], v2["SDS"])
    SD1 = linear_interp(r, r1, r2, v1["SD1"], v2["SD1"])
    SMS = linear_interp(r, r1, r2, v1["SMS"], v2["SMS"])
    SM1 = linear_interp(r, r1, r2, v1["SM1"], v2["SM1"])

    T0D = round(SD1 / SDS, 3)
    T0M = round(SM1 / SMS, 3)
    T_T0D = round(T / T0D, 3)
    T_T0M = round(T / T0M, 3)

    Fu = calculate_fu(R, T_T0D)
    FuM = calculate_fu(R, T_T0M)

    SaD = SDS
    SaM = SMS
    V = round((I * (SaD / Fu)) / (1.4 * alpha_y) * W, 2)
    VM = round((I * (SaM / FuM)) / 1.4 * W, 2)

    summary = f"位於 {location} 之建物，對應斷層 {fault_name}，距離 {r} km，週期 {T} sec，計算得：\n"
    summary += f"SDS = {SDS}, SD1 = {SD1}, Fu = {Fu}, 設計地震力 V = {V} kN，最大地震力 VM = {VM} kN"

    return {
        "location": location,
        "fault_name": fault_name,
        "distance_km": r,
        "input": {
            "T": T, "R": R, "I": I, "alpha_y": alpha_y, "W": W
        },
        "coefficients": {
            "SDS": SDS, "SD1": SD1, "SMS": SMS, "SM1": SM1
        },
        "intermediate": {
            "T0D": T0D, "T0M": T0M, "T/T0D": T_T0D, "T/T0M": T_T0M,
            "Fu": Fu, "FuM": FuM, "SaD": SaD, "SaM": SaM
        },
        "results": {
            "V": V,
            "VM": VM
        },
        "summary": summary
    }

if __name__ == "__main__":
    uvicorn.run("seismic_report:app", host="0.0.0.0", port=8000, reload=True)
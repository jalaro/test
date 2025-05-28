from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import json
import uvicorn

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

@app.get("/seismic_kx")
def seismic_kx(
    fault_name: str = Query(...),
    distance_km: float = Query(...),
    direction: str = Query(..., regex="^(X|Y)$"),
    T: float = Query(...),
    R: float = Query(...),
    I: float = Query(...),
    alpha_y: float = Query(...),
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
    T_T0D = round(T / T0D, 3)
    Fu = calculate_fu(R, T_T0D)

    # 依序計算四種水平地震力係數
    K_main = round((I * (SDS / Fu)) / (1.4 * alpha_y), 5)
    K_moderate = round((I * SDS) / (R * alpha_y), 5)
    K_maximum = round((I * SMS) / (R * alpha_y), 5)
    K_collapse = round((I * SM1) / (R * alpha_y), 5)

    K_label = "Kx" if direction == "X" else "Ky"

    return {
        "direction": direction,
        "location": location,
        "fault_name": fault_name,
        "distance_km": r,
        "input": {
            "T": T, "R": R, "I": I, "alpha_y": alpha_y
        },
        "coefficients": {
            "SDS": SDS, "SD1": SD1, "SMS": SMS, "SM1": SM1, "Fu": Fu
        },
        f"{K_label}_table": [
            {"方向": direction, "類型": f"{K_label}：最小設計水平方向地震力係數", "公式": f"{K_label} = I × (SDS / Fu) ÷ (1.4 × αy)", "值": K_main},
            {"方向": direction, "類型": f"{K_label}：中小度地震設計地震力係數", "公式": f"{K_label}_moderate = I × SDS ÷ (R × αy)", "值": K_moderate},
            {"方向": direction, "類型": f"{K_label}：最大考量地震設計地震力係數", "公式": f"{K_label}_maximum = I × SMS ÷ (R × αy)", "值": K_maximum},
            {"方向": direction, "類型": f"{K_label}：避免崩塌設計地震力係數", "公式": f"{K_label}_collapse = I × SM1 ÷ (R × αy)", "值": K_collapse}
        ],
        "summary": f"{K_label} = ({I} × ({SDS} / {Fu})) ÷ (1.4 × {alpha_y}) = {K_main}"
    }
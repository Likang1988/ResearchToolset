//! 间接经费计算器（对应 `app/tools/IndirectCostCalculator.py::calculate_max_indirect_cost`）
//!
//! 规则：间接经费基数 = 直接经费 - 设备费 - 外协费；
//! 分档费率（默认 500 万内 20%、500-1000 万 15%、1000 万以上 13%），
//! 用二分法求满足 `直接经费 + 间接经费 <= 总经费` 的最大间接经费。

/// 计算最大间接经费（万元）。
///
/// - `total_funds`：总经费（万元）
/// - `equipment_cost`：设备费（万元）
/// - `external_cooperation_cost`：外协费（万元）
/// - 费率均以小数传入（如 20% 传 0.20）
///
/// 与 Python 版算法逐语句一致（含 0.01 收敛精度与 `total_funds - left` 的返回方式）。
pub fn calculate_max_indirect_cost(
    total_funds: f64,
    equipment_cost: f64,
    external_cooperation_cost: f64,
    rate1: f64,
    rate2: f64,
    rate3: f64,
) -> f64 {
    fn calc_indirect(
        direct: f64,
        equipment_cost: f64,
        external_cooperation_cost: f64,
        rate1: f64,
        rate2: f64,
        rate3: f64,
    ) -> f64 {
        let base = direct - equipment_cost - external_cooperation_cost;
        if base <= 500.0 {
            base * rate1
        } else if base <= 1000.0 {
            500.0 * rate1 + (base - 500.0) * rate2
        } else {
            500.0 * rate1 + 500.0 * rate2 + (base - 1000.0) * rate3
        }
    }

    let mut left = 0.0;
    let mut right = total_funds;
    while right - left > 0.01 {
        let mid = (left + right) / 2.0;
        if mid + calc_indirect(mid, equipment_cost, external_cooperation_cost, rate1, rate2, rate3)
            > total_funds
        {
            right = mid;
        } else {
            left = mid;
        }
    }

    total_funds - left
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 与 Python 版对拍基准（默认费率）
    /// Python: calculate_max_indirect_cost(100, 20, 10, 0.2, 0.15, 0.13)
    /// 直接经费 x：x + (x-30)*0.2 <= 100 → x <= 88.3333 → 间接 = 11.6667
    #[test]
    fn matches_python_reference() {
        let r = calculate_max_indirect_cost(100.0, 20.0, 10.0, 0.20, 0.15, 0.13);
        assert!((r - 11.666666666666657).abs() < 0.01, "实际值 {r}");
    }

    #[test]
    fn zero_funds_gives_zero() {
        let r = calculate_max_indirect_cost(0.0, 0.0, 0.0, 0.2, 0.15, 0.13);
        assert_eq!(r, 0.0);
    }

    #[test]
    fn tiered_rates_boundary_500() {
        // 直接经费 500 整：500*0.2 = 100 间接 → 总 600
        // total=600 时最大间接 ≈ 100
        let r = calculate_max_indirect_cost(600.0, 0.0, 0.0, 0.20, 0.15, 0.13);
        assert!((r - 100.0).abs() < 0.01, "实际值 {r}");
    }
}

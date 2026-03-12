import Foundation

struct CheckoutScenario {
    let subtotalCents: Int
    let couponCode: String
    let expectedDiscountPercent: Int

    var expectedDiscountCents: Int {
        (subtotalCents * expectedDiscountPercent) / 100
    }

    var expectedTotalCents: Int {
        subtotalCents - expectedDiscountCents
    }
}

struct CheckoutQuote {
    let subtotalCents: Int
    let pendingCouponCode: String?
    let appliedCouponCode: String?
    let policyCouponCode: String?
    let policyDiscountPercent: Int
    let discountCents: Int
    let totalCents: Int
}

struct CheckoutContext {
    let pendingCouponCode: String?
    let appliedCouponCode: String?
}

final class CheckoutContextStore {
    private(set) var current = CheckoutContext(pendingCouponCode: nil, appliedCouponCode: nil)

    func selectCoupon(_ couponCode: String) {
        current = CheckoutContext(
            pendingCouponCode: couponCode,
            appliedCouponCode: current.appliedCouponCode
        )
    }

    func applyPendingCoupon() {
        current = CheckoutContext(
            pendingCouponCode: current.pendingCouponCode,
            appliedCouponCode: current.pendingCouponCode
        )
    }
}

struct PricingPolicy {
    let couponCode: String?
    let discountPercent: Int
}

struct PricingPolicyRepository {
    private let contextStore: CheckoutContextStore

    init(contextStore: CheckoutContextStore) {
        self.contextStore = contextStore
    }

    func activePolicy() -> PricingPolicy {
        let couponCode = contextStore.current.appliedCouponCode
        let discountPercent = couponCode == "SAVE20" ? 20 : 0
        return PricingPolicy(couponCode: couponCode, discountPercent: discountPercent)
    }

    func livePendingCouponCode() -> String? {
        contextStore.current.pendingCouponCode
    }

    func liveAppliedCouponCode() -> String? {
        contextStore.current.appliedCouponCode
    }
}

struct CheckoutUseCase {
    private let pricingEngine = PricingEngine()
    private let policyRepository: PricingPolicyRepository

    init(policyRepository: PricingPolicyRepository) {
        self.policyRepository = policyRepository
    }

    func makeQuote(subtotalCents: Int) -> CheckoutQuote {
        let policy = policyRepository.activePolicy()
        let discountCents = pricingEngine.discountCents(subtotalCents: subtotalCents, discountPercent: policy.discountPercent)
        let totalCents = subtotalCents - discountCents

        return CheckoutQuote(
            subtotalCents: subtotalCents,
            pendingCouponCode: policyRepository.livePendingCouponCode(),
            appliedCouponCode: policyRepository.liveAppliedCouponCode(),
            policyCouponCode: policy.couponCode,
            policyDiscountPercent: policy.discountPercent,
            discountCents: discountCents,
            totalCents: totalCents
        )
    }
}

struct PricingEngine {
    private let discountCalculator = DiscountCalculator()

    func discountCents(subtotalCents: Int, discountPercent: Int) -> Int {
        discountCalculator.discountAmount(
            subtotalCents: subtotalCents,
            discountPercent: discountPercent
        )
    }
}

struct DiscountCalculator {
    func discountAmount(subtotalCents: Int, discountPercent: Int) -> Int {
        (subtotalCents * discountPercent) / 100
    }
}

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
    let contextCouponCode: String?
    let policyCouponCode: String?
    let policyDiscountPercent: Int
    let discountCents: Int
    let totalCents: Int
}

struct CheckoutContext {
    let couponCode: String?
}

final class CheckoutContextStore {
    private(set) var current = CheckoutContext(couponCode: nil)

    func applyCoupon(_ couponCode: String) {
        current = CheckoutContext(couponCode: couponCode)
    }
}

struct PricingPolicy {
    let couponCode: String?
    let discountPercent: Int
}

struct PricingPolicyRepository {
    private let contextStore: CheckoutContextStore
    private let cachedContext: CheckoutContext

    init(contextStore: CheckoutContextStore) {
        self.contextStore = contextStore
        self.cachedContext = contextStore.current
    }

    func activePolicy() -> PricingPolicy {
        // Intentional bug: stale context snapshot is used instead of live context.
        let couponCode = cachedContext.couponCode
        let discountPercent = couponCode == "SAVE20" ? 20 : 0
        return PricingPolicy(couponCode: couponCode, discountPercent: discountPercent)
    }

    func liveContextCouponCode() -> String? {
        contextStore.current.couponCode
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
            contextCouponCode: policyRepository.liveContextCouponCode(),
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

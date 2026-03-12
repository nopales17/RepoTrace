import Foundation

struct DeliveryScenario {
    let standardLeadDays: Int
    let speedCode: String
    let expectedLeadDays: Int
}

struct DeliveryQuote {
    let standardLeadDays: Int
    let pendingSpeedCode: String?
    let appliedSpeedCode: String?
    let policySpeedCode: String?
    let policyLeadDays: Int
    let promisedLeadDays: Int
}

struct DeliveryContext {
    let pendingSpeedCode: String?
    let appliedSpeedCode: String?
}

final class DeliveryContextStore {
    private(set) var current = DeliveryContext(pendingSpeedCode: nil, appliedSpeedCode: nil)

    func selectSpeed(_ speedCode: String) {
        current = DeliveryContext(
            pendingSpeedCode: speedCode,
            appliedSpeedCode: current.appliedSpeedCode
        )
    }

    func applyPendingSpeed() {
        current = DeliveryContext(
            pendingSpeedCode: current.pendingSpeedCode,
            appliedSpeedCode: current.pendingSpeedCode
        )
    }
}

struct FulfillmentPolicy {
    let speedCode: String?
    let leadDays: Int
}

struct FulfillmentPolicyRepository {
    private let contextStore: DeliveryContextStore

    init(contextStore: DeliveryContextStore) {
        self.contextStore = contextStore
    }

    func activePolicy(standardLeadDays: Int) -> FulfillmentPolicy {
        let speedCode = contextStore.current.appliedSpeedCode
        let leadDays = speedCode == "EXPRESS" ? 1 : standardLeadDays
        return FulfillmentPolicy(speedCode: speedCode, leadDays: leadDays)
    }

    func livePendingSpeedCode() -> String? {
        contextStore.current.pendingSpeedCode
    }

    func liveAppliedSpeedCode() -> String? {
        contextStore.current.appliedSpeedCode
    }
}

struct DeliveryPromiseUseCase {
    private let promiseEngine = PromiseEngine()
    private let policyRepository: FulfillmentPolicyRepository

    init(policyRepository: FulfillmentPolicyRepository) {
        self.policyRepository = policyRepository
    }

    func makeQuote(standardLeadDays: Int) -> DeliveryQuote {
        let policy = policyRepository.activePolicy(standardLeadDays: standardLeadDays)
        let promisedLeadDays = promiseEngine.promisedLeadDays(
            standardLeadDays: standardLeadDays,
            policyLeadDays: policy.leadDays
        )

        return DeliveryQuote(
            standardLeadDays: standardLeadDays,
            pendingSpeedCode: policyRepository.livePendingSpeedCode(),
            appliedSpeedCode: policyRepository.liveAppliedSpeedCode(),
            policySpeedCode: policy.speedCode,
            policyLeadDays: policy.leadDays,
            promisedLeadDays: promisedLeadDays
        )
    }
}

struct PromiseEngine {
    private let promiseCalculator = PromiseCalculator()

    func promisedLeadDays(standardLeadDays: Int, policyLeadDays: Int) -> Int {
        promiseCalculator.promisedLeadDays(
            standardLeadDays: standardLeadDays,
            policyLeadDays: policyLeadDays
        )
    }
}

struct PromiseCalculator {
    func promisedLeadDays(standardLeadDays: Int, policyLeadDays: Int) -> Int {
        min(standardLeadDays, policyLeadDays)
    }
}

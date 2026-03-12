import Foundation

struct NotificationScenario {
    let baselineDispatchCount: Int
    let preferenceKey: String
    let preferenceLabel: String
    let expectedDispatchCount: Int
}

struct NotificationDispatchQuote {
    let baselineDispatchCount: Int
    let selectedPreferenceKey: String?
    let activePreferenceKey: String?
    let policyPreferenceKey: String?
    let policyAllowedCount: Int
    let dispatchedCount: Int
}

struct NotificationPreferenceContext {
    let selectedPreferenceKey: String?
    let activePreferenceKey: String?
}

final class NotificationPreferenceStore {
    private(set) var current = NotificationPreferenceContext(selectedPreferenceKey: nil, activePreferenceKey: nil)

    func selectPreference(_ preferenceKey: String) {
        current = NotificationPreferenceContext(
            selectedPreferenceKey: preferenceKey,
            activePreferenceKey: current.activePreferenceKey
        )
    }

    func activateSelectedPreference() {
        current = NotificationPreferenceContext(
            selectedPreferenceKey: current.selectedPreferenceKey,
            activePreferenceKey: current.selectedPreferenceKey
        )
    }
}

struct NotificationDispatchPolicy {
    let preferenceKey: String?
    let allowedCount: Int
}

struct NotificationDispatchPolicyRepository {
    private let preferenceStore: NotificationPreferenceStore

    init(preferenceStore: NotificationPreferenceStore) {
        self.preferenceStore = preferenceStore
    }

    func activePolicy(baselineDispatchCount: Int) -> NotificationDispatchPolicy {
        let preferenceKey = preferenceStore.current.activePreferenceKey
        let allowedCount = preferenceKey == "SECURITY_ALERTS" ? baselineDispatchCount : 0
        return NotificationDispatchPolicy(preferenceKey: preferenceKey, allowedCount: allowedCount)
    }

    func liveSelectedPreferenceKey() -> String? {
        preferenceStore.current.selectedPreferenceKey
    }

    func liveActivePreferenceKey() -> String? {
        preferenceStore.current.activePreferenceKey
    }
}

struct NotificationDispatchUseCase {
    private let dispatchEngine = NotificationDispatchEngine()
    private let policyRepository: NotificationDispatchPolicyRepository

    init(policyRepository: NotificationDispatchPolicyRepository) {
        self.policyRepository = policyRepository
    }

    func makePreview(baselineDispatchCount: Int) -> NotificationDispatchQuote {
        let policy = policyRepository.activePolicy(baselineDispatchCount: baselineDispatchCount)
        let dispatchedCount = dispatchEngine.dispatchedCount(
            baselineDispatchCount: baselineDispatchCount,
            policyAllowedCount: policy.allowedCount
        )

        return NotificationDispatchQuote(
            baselineDispatchCount: baselineDispatchCount,
            selectedPreferenceKey: policyRepository.liveSelectedPreferenceKey(),
            activePreferenceKey: policyRepository.liveActivePreferenceKey(),
            policyPreferenceKey: policy.preferenceKey,
            policyAllowedCount: policy.allowedCount,
            dispatchedCount: dispatchedCount
        )
    }
}

struct NotificationDispatchEngine {
    private let dispatchCalculator = NotificationDispatchCalculator()

    func dispatchedCount(baselineDispatchCount: Int, policyAllowedCount: Int) -> Int {
        dispatchCalculator.dispatchedCount(
            baselineDispatchCount: baselineDispatchCount,
            policyAllowedCount: policyAllowedCount
        )
    }
}

struct NotificationDispatchCalculator {
    func dispatchedCount(baselineDispatchCount: Int, policyAllowedCount: Int) -> Int {
        min(baselineDispatchCount, policyAllowedCount)
    }
}

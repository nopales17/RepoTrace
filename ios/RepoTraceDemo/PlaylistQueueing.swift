import Foundation

struct PlaylistQueueScenario {
    let libraryTrackCount: Int
    let collectionCode: String
    let collectionLabel: String
    let expectedQueuedTrackCount: Int
}

struct PlaylistQueuePreview {
    let libraryTrackCount: Int
    let screenCollectionCode: String?
    let runtimeCollectionCode: String?
    let ruleCollectionCode: String?
    let ruleMatchKey: String
    let ruleQueuedTrackCount: Int
    let queuedTrackCount: Int
}

struct PlaylistQueueState {
    let screenCollectionCode: String?
    let runtimeCollectionCode: String?
}

final class PlaylistQueueStore {
    private(set) var current = PlaylistQueueState(screenCollectionCode: nil, runtimeCollectionCode: nil)

    func chooseCollection(_ collectionCode: String) {
        current = PlaylistQueueState(
            screenCollectionCode: collectionCode,
            runtimeCollectionCode: current.runtimeCollectionCode
        )
    }

    func promoteRuntimeCollection() {
        current = PlaylistQueueState(
            screenCollectionCode: current.screenCollectionCode,
            runtimeCollectionCode: current.screenCollectionCode
        )
    }
}

struct PlaylistQueueRule {
    let collectionCode: String?
    let matchKey: String
    let queuedTrackCount: Int
}

struct PlaylistQueueRulebook {
    private static let roadTripRuleKey = "ROADTRIP_MIX"
    private let queueStore: PlaylistQueueStore

    init(queueStore: PlaylistQueueStore) {
        self.queueStore = queueStore
    }

    func resolve(libraryTrackCount: Int) -> PlaylistQueueRule {
        let collectionCode = queueStore.current.runtimeCollectionCode
        let queuedTrackCount = collectionCode == Self.roadTripRuleKey ? libraryTrackCount : 0
        return PlaylistQueueRule(
            collectionCode: collectionCode,
            matchKey: Self.roadTripRuleKey,
            queuedTrackCount: queuedTrackCount
        )
    }

    func liveScreenCollectionCode() -> String? {
        queueStore.current.screenCollectionCode
    }

    func liveRuntimeCollectionCode() -> String? {
        queueStore.current.runtimeCollectionCode
    }
}

struct PlaylistQueuePreviewUseCase {
    private let queueEngine = PlaylistQueueEngine()
    private let queueRulebook: PlaylistQueueRulebook

    init(queueRulebook: PlaylistQueueRulebook) {
        self.queueRulebook = queueRulebook
    }

    func makePreview(libraryTrackCount: Int) -> PlaylistQueuePreview {
        let rule = queueRulebook.resolve(libraryTrackCount: libraryTrackCount)
        let queuedTrackCount = queueEngine.queuedTrackCount(
            libraryTrackCount: libraryTrackCount,
            ruleQueuedTrackCount: rule.queuedTrackCount
        )

        return PlaylistQueuePreview(
            libraryTrackCount: libraryTrackCount,
            screenCollectionCode: queueRulebook.liveScreenCollectionCode(),
            runtimeCollectionCode: queueRulebook.liveRuntimeCollectionCode(),
            ruleCollectionCode: rule.collectionCode,
            ruleMatchKey: rule.matchKey,
            ruleQueuedTrackCount: rule.queuedTrackCount,
            queuedTrackCount: queuedTrackCount
        )
    }
}

struct PlaylistQueueEngine {
    private let queueMath = PlaylistQueueMath()

    func queuedTrackCount(libraryTrackCount: Int, ruleQueuedTrackCount: Int) -> Int {
        queueMath.queuedTrackCount(
            libraryTrackCount: libraryTrackCount,
            ruleQueuedTrackCount: ruleQueuedTrackCount
        )
    }
}

struct PlaylistQueueMath {
    func queuedTrackCount(libraryTrackCount: Int, ruleQueuedTrackCount: Int) -> Int {
        min(libraryTrackCount, ruleQueuedTrackCount)
    }
}

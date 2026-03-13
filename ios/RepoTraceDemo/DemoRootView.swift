import SwiftUI

struct DemoRootView: View {
    private let scenario = PlaylistQueueScenario(
        libraryTrackCount: 4,
        collectionCode: "ROAD_TRIP_MIX",
        collectionLabel: "Road Trip Mix",
        expectedQueuedTrackCount: 4
    )
    private let queueStore: PlaylistQueueStore
    private let queuePreviewUseCase: PlaylistQueuePreviewUseCase

    @State private var displayedCollectionCode: String?
    @State private var latestPreview: PlaylistQueuePreview?

    init() {
        let store = PlaylistQueueStore()
        self.queueStore = store
        self.queuePreviewUseCase = PlaylistQueuePreviewUseCase(
            queueRulebook: PlaylistQueueRulebook(queueStore: store)
        )
    }

    var body: some View {
        NavigationStack {
            VStack(spacing: 16) {
                Text("RepoTrace Demo")
                    .font(.title2)
                    .fontWeight(.semibold)

                Text("Offline queue preview")
                    .multilineTextAlignment(.center)

                Text("Library candidates: \(tracksLabel(scenario.libraryTrackCount))")
                Text("Expected with \(scenario.collectionLabel): \(tracksLabel(scenario.expectedQueuedTrackCount))")
                Text("Collection shown in UI: \(labelForCollection(displayedCollectionCode))")

                if let latestPreview {
                    Text("Actual queue preview: \(tracksLabel(latestPreview.queuedTrackCount))")
                        .foregroundColor(latestPreview.queuedTrackCount == scenario.expectedQueuedTrackCount ? .green : .red)
                }

                Button("Pick Road Trip Mix") {
                    runPlaylistQueueScenario()
                }
                .buttonStyle(.borderedProminent)
            }
            .padding()
            .navigationTitle("Home")
            .repoTraceDebugReportEntryPoint()
        }
        .onAppear {
            BreadcrumbStore.shared.add("Opened demo root", category: "navigation")
        }
    }

    private func runPlaylistQueueScenario() {
        queueStore.chooseCollection(scenario.collectionCode)
        queueStore.promoteRuntimeCollection()
        displayedCollectionCode = queueStore.current.screenCollectionCode

        BreadcrumbStore.shared.add(
            "Tapped pick collection, uiCollection=\(displayedCollectionCode ?? "none"), libraryTrackCount=\(scenario.libraryTrackCount)",
            category: "action"
        )

        BreadcrumbStore.shared.add(
            "Collection snapshot: screenCollection=\(queueStore.current.screenCollectionCode ?? "nil"), runtimeCollection=\(queueStore.current.runtimeCollectionCode ?? "nil")",
            category: "context"
        )

        let preview = queuePreviewUseCase.makePreview(libraryTrackCount: scenario.libraryTrackCount)
        latestPreview = preview

        BreadcrumbStore.shared.add(
            "Queue rule used: collectionCode=\(preview.ruleCollectionCode ?? "nil"), matchKey=\(preview.ruleMatchKey), queuedTrackCount=\(preview.ruleQueuedTrackCount)",
            category: "pipeline"
        )

        BreadcrumbStore.shared.add(
            "Queue engine result: queuedTrackCount=\(preview.queuedTrackCount)",
            category: "pipeline"
        )

        BreadcrumbStore.shared.add(
            "Observed UI state: expectedCollection=\(scenario.collectionCode), displayedCollection=\(displayedCollectionCode ?? "none")",
            category: "observation"
        )

        BreadcrumbStore.shared.add(
            "Observed preview values: ruleMatchKey=\(preview.ruleMatchKey), ruleQueuedTrackCount=\(preview.ruleQueuedTrackCount), expectedQueuedTrackCount=\(scenario.expectedQueuedTrackCount), actualQueuedTrackCount=\(preview.queuedTrackCount)",
            category: "observation"
        )

        BreadcrumbStore.shared.add(
            "Observed state values: screenCollection=\(preview.screenCollectionCode ?? "nil"), runtimeCollection=\(preview.runtimeCollectionCode ?? "nil"), ruleCollection=\(preview.ruleCollectionCode ?? "nil")",
            category: "observation"
        )

        if preview.queuedTrackCount != scenario.expectedQueuedTrackCount {
            BreadcrumbStore.shared.add(
                "Queue preview mismatch: expectedQueuedTrackCount=\(scenario.expectedQueuedTrackCount), actualQueuedTrackCount=\(preview.queuedTrackCount)",
                category: "bug"
            )

            DebugReportDraftStore.shared.stage(
                DebugReportDraft(
                    title: "Collection appears picked but queue preview is unchanged",
                    expectedBehavior: "After picking \(scenario.collectionLabel), queue preview should show \(tracksLabel(scenario.expectedQueuedTrackCount)).",
                    actualBehavior: "UI shows collection \(labelForCollection(displayedCollectionCode)), but queue preview is \(tracksLabel(preview.queuedTrackCount)).",
                    reporterNotes: "ScreenCollection=\(preview.screenCollectionCode ?? "nil"), RuntimeCollection=\(preview.runtimeCollectionCode ?? "nil"), RuleCollection=\(preview.ruleCollectionCode ?? "nil"), RuleMatchKey=\(preview.ruleMatchKey), RuleQueuedTrackCount=\(preview.ruleQueuedTrackCount).",
                    screenName: "DownloadHome"
                )
            )
        }
    }

    private func tracksLabel(_ count: Int) -> String {
        if count == 1 {
            return "1 track"
        }

        return "\(count) tracks"
    }

    private func labelForCollection(_ code: String?) -> String {
        switch code {
        case scenario.collectionCode:
            return scenario.collectionLabel
        case nil:
            return "none"
        default:
            return code ?? "none"
        }
    }
}

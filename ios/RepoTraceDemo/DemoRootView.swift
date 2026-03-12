import SwiftUI

struct DemoRootView: View {
    private let scenario = NotificationScenario(
        baselineDispatchCount: 2,
        preferenceKey: "SECURITY_ALERTS",
        preferenceLabel: "Security Alerts",
        expectedDispatchCount: 2
    )
    private let preferenceStore: NotificationPreferenceStore
    private let dispatchUseCase: NotificationDispatchUseCase

    @State private var displayedPreferenceKey: String?
    @State private var latestQuote: NotificationDispatchQuote?

    init() {
        let store = NotificationPreferenceStore()
        self.preferenceStore = store
        self.dispatchUseCase = NotificationDispatchUseCase(
            policyRepository: NotificationDispatchPolicyRepository(preferenceStore: store)
        )
    }

    var body: some View {
        NavigationStack {
            VStack(spacing: 16) {
                Text("RepoTrace Demo")
                    .font(.title2)
                    .fontWeight(.semibold)

                Text("Notification preference preview")
                    .multilineTextAlignment(.center)

                Text("Base dispatch batch: \(alertsLabel(scenario.baselineDispatchCount))")
                Text("Expected with \(scenario.preferenceLabel): \(alertsLabel(scenario.expectedDispatchCount))")
                Text("Preference shown in UI: \(labelForPreference(displayedPreferenceKey))")

                if let latestQuote {
                    Text("Actual dispatch preview: \(alertsLabel(latestQuote.dispatchedCount))")
                        .foregroundColor(latestQuote.dispatchedCount == scenario.expectedDispatchCount ? .green : .red)
                }

                Button("Select Security Alerts") {
                    runNotificationPreferenceScenario()
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

    private func runNotificationPreferenceScenario() {
        preferenceStore.selectPreference(scenario.preferenceKey)
        displayedPreferenceKey = preferenceStore.current.selectedPreferenceKey

        BreadcrumbStore.shared.add(
            "Tapped select preference, uiPreference=\(displayedPreferenceKey ?? "none"), baselineDispatchCount=\(scenario.baselineDispatchCount)",
            category: "action"
        )

        BreadcrumbStore.shared.add(
            "Preference selection updated: selectedPreference=\(preferenceStore.current.selectedPreferenceKey ?? "nil"), activePreference=\(preferenceStore.current.activePreferenceKey ?? "nil")",
            category: "context"
        )

        let quote = dispatchUseCase.makePreview(baselineDispatchCount: scenario.baselineDispatchCount)
        latestQuote = quote

        BreadcrumbStore.shared.add(
            "Dispatch policy used: preferenceKey=\(quote.policyPreferenceKey ?? "nil"), allowedCount=\(quote.policyAllowedCount)",
            category: "pipeline"
        )

        BreadcrumbStore.shared.add(
            "Dispatch engine result: dispatchedCount=\(quote.dispatchedCount)",
            category: "pipeline"
        )

        BreadcrumbStore.shared.add(
            "Triage UI check: expectedUiPreference=\(scenario.preferenceKey), displayedPreference=\(displayedPreferenceKey ?? "none")",
            category: "triage"
        )

        BreadcrumbStore.shared.add(
            "Triage arithmetic check: policyAllowedCount=\(quote.policyAllowedCount), expectedDispatchCount=\(scenario.expectedDispatchCount), actualDispatchCount=\(quote.dispatchedCount)",
            category: "triage"
        )

        BreadcrumbStore.shared.add(
            "Triage source-of-truth check: selectedPreference=\(quote.selectedPreferenceKey ?? "nil"), activePreference=\(quote.activePreferenceKey ?? "nil"), policyPreference=\(quote.policyPreferenceKey ?? "nil")",
            category: "triage"
        )

        let classification = classifyBug(from: quote)

        if quote.dispatchedCount != scenario.expectedDispatchCount {
            BreadcrumbStore.shared.add(
                "Preview mismatch: expectedDispatchCount=\(scenario.expectedDispatchCount), actualDispatchCount=\(quote.dispatchedCount)",
                category: "bug"
            )

            DebugReportDraftStore.shared.stage(
                DebugReportDraft(
                    title: "Preference appears selected but dispatch preview is unchanged",
                    expectedBehavior: "After selecting \(scenario.preferenceLabel), dispatch preview should show \(alertsLabel(scenario.expectedDispatchCount)).",
                    actualBehavior: "UI shows preference \(labelForPreference(displayedPreferenceKey)), but dispatch preview is \(alertsLabel(quote.dispatchedCount)).",
                    reporterNotes: "Classification=\(classification). SelectedPreference=\(quote.selectedPreferenceKey ?? "nil"), ActivePreference=\(quote.activePreferenceKey ?? "nil"), PolicyPreference=\(quote.policyPreferenceKey ?? "nil"), PolicyAllowedCount=\(quote.policyAllowedCount).",
                    screenName: "DemoHome"
                )
            )
        }
    }

    private func classifyBug(from quote: NotificationDispatchQuote) -> String {
        if displayedPreferenceKey != scenario.preferenceKey {
            return "ui-only"
        }

        if quote.policyAllowedCount == scenario.expectedDispatchCount &&
            quote.dispatchedCount != scenario.expectedDispatchCount {
            return "arithmetic-logic"
        }

        if quote.selectedPreferenceKey == scenario.preferenceKey &&
            quote.activePreferenceKey != scenario.preferenceKey &&
            quote.policyPreferenceKey != scenario.preferenceKey {
            return "source-of-truth-divergence"
        }

        return "unknown"
    }

    private func alertsLabel(_ count: Int) -> String {
        if count == 1 {
            return "1 alert"
        }

        return "\(count) alerts"
    }

    private func labelForPreference(_ key: String?) -> String {
        switch key {
        case scenario.preferenceKey:
            return scenario.preferenceLabel
        case nil:
            return "none"
        default:
            return key ?? "none"
        }
    }
}

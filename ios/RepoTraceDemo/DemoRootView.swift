import SwiftUI

struct DemoRootView: View {
    private let scenario = DeliveryScenario(standardLeadDays: 3, speedCode: "EXPRESS", expectedLeadDays: 1)
    private let contextStore: DeliveryContextStore
    private let deliveryPromiseUseCase: DeliveryPromiseUseCase

    @State private var displayedSpeedCode: String?
    @State private var latestQuote: DeliveryQuote?
    @State private var bugClassification: String?

    init() {
        let store = DeliveryContextStore()
        self.contextStore = store
        self.deliveryPromiseUseCase = DeliveryPromiseUseCase(policyRepository: FulfillmentPolicyRepository(contextStore: store))
    }

    var body: some View {
        NavigationStack {
            VStack(spacing: 16) {
                Text("RepoTrace Demo")
                    .font(.title2)
                    .fontWeight(.semibold)

                Text("Fake bug: UI shows EXPRESS selected, but promise remains standard.")
                    .multilineTextAlignment(.center)

                Text("Standard delivery promise: \(daysLabel(scenario.standardLeadDays))")
                Text("Expected with \(scenario.speedCode): \(daysLabel(scenario.expectedLeadDays))")
                Text("Speed shown in UI: \(displayedSpeedCode ?? "none")")

                if let latestQuote {
                    Text("Actual promised delivery: \(daysLabel(latestQuote.promisedLeadDays))")
                        .foregroundColor(latestQuote.promisedLeadDays == scenario.expectedLeadDays ? .green : .red)
                }

                if let bugClassification {
                    Text("Bug classification: \(bugClassification)")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }

                Button("Select EXPRESS (Buggy)") {
                    runDeliveryBugScenario()
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

    private func runDeliveryBugScenario() {
        contextStore.selectSpeed(scenario.speedCode)
        displayedSpeedCode = contextStore.current.pendingSpeedCode

        BreadcrumbStore.shared.add(
            "Tapped select speed, uiSpeed=\(displayedSpeedCode ?? "none"), standardLeadDays=\(scenario.standardLeadDays)",
            category: "action"
        )

        BreadcrumbStore.shared.add(
            "Delivery selection updated: pendingSpeed=\(contextStore.current.pendingSpeedCode ?? "nil"), appliedSpeed=\(contextStore.current.appliedSpeedCode ?? "nil")",
            category: "context"
        )

        let quote = deliveryPromiseUseCase.makeQuote(standardLeadDays: scenario.standardLeadDays)
        latestQuote = quote

        BreadcrumbStore.shared.add(
            "Fulfillment policy used: speedCode=\(quote.policySpeedCode ?? "nil"), leadDays=\(quote.policyLeadDays)",
            category: "pipeline"
        )

        BreadcrumbStore.shared.add(
            "Promise engine result: promisedLeadDays=\(quote.promisedLeadDays)",
            category: "pipeline"
        )

        BreadcrumbStore.shared.add(
            "Triage UI check: expectedUiSpeed=\(scenario.speedCode), displayedSpeed=\(displayedSpeedCode ?? "none")",
            category: "triage"
        )

        BreadcrumbStore.shared.add(
            "Triage arithmetic check: policyLeadDays=\(quote.policyLeadDays), expectedLeadDays=\(scenario.expectedLeadDays), expectedPromisedLeadDays=\(scenario.expectedLeadDays), actualPromisedLeadDays=\(quote.promisedLeadDays)",
            category: "triage"
        )

        BreadcrumbStore.shared.add(
            "Triage source-of-truth check: pendingSpeed=\(quote.pendingSpeedCode ?? "nil"), appliedSpeed=\(quote.appliedSpeedCode ?? "nil"), policySpeed=\(quote.policySpeedCode ?? "nil")",
            category: "triage"
        )

        let classification = classifyBug(from: quote)
        bugClassification = classification

        if quote.promisedLeadDays != scenario.expectedLeadDays {
            BreadcrumbStore.shared.add(
                "Bug observed: class=\(classification), expectedLeadDays=\(scenario.expectedLeadDays), actualLeadDays=\(quote.promisedLeadDays)",
                category: "bug"
            )

            DebugReportDraftStore.shared.stage(
                DebugReportDraft(
                    title: "Express appears selected but promise remains standard",
                    expectedBehavior: "After selecting \(scenario.speedCode), promised delivery should change from \(daysLabel(scenario.standardLeadDays)) to \(daysLabel(scenario.expectedLeadDays)).",
                    actualBehavior: "UI shows speed \(displayedSpeedCode ?? "none"), but promised delivery is \(daysLabel(quote.promisedLeadDays)).",
                    reporterNotes: "Classification=\(classification). PendingSpeed=\(quote.pendingSpeedCode ?? "nil"), AppliedSpeed=\(quote.appliedSpeedCode ?? "nil"), PolicySpeed=\(quote.policySpeedCode ?? "nil"), PolicyLeadDays=\(quote.policyLeadDays).",
                    screenName: "DemoHome"
                )
            )
        }
    }

    private func classifyBug(from quote: DeliveryQuote) -> String {
        if displayedSpeedCode != scenario.speedCode {
            return "ui-only"
        }

        if quote.policyLeadDays == scenario.expectedLeadDays &&
            quote.promisedLeadDays != scenario.expectedLeadDays {
            return "arithmetic-logic"
        }

        if quote.pendingSpeedCode == scenario.speedCode &&
            quote.appliedSpeedCode != scenario.speedCode &&
            quote.policySpeedCode != scenario.speedCode {
            return "source-of-truth-divergence"
        }

        return "unknown"
    }

    private func daysLabel(_ days: Int) -> String {
        if days == 1 {
            return "1 day"
        }

        return "\(days) days"
    }
}

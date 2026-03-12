import SwiftUI

struct DemoRootView: View {
    private let scenario = CheckoutScenario(subtotalCents: 2_500, couponCode: "SAVE20", expectedDiscountPercent: 20)
    private let contextStore: CheckoutContextStore
    private let checkoutUseCase: CheckoutUseCase

    @State private var displayedCouponCode: String?
    @State private var latestQuote: CheckoutQuote?
    @State private var bugClassification: String?

    init() {
        let store = CheckoutContextStore()
        self.contextStore = store
        self.checkoutUseCase = CheckoutUseCase(policyRepository: PricingPolicyRepository(contextStore: store))
    }

    var body: some View {
        NavigationStack {
            VStack(spacing: 16) {
                Text("RepoTrace Demo")
                    .font(.title2)
                    .fontWeight(.semibold)

                Text("Fake bug: UI shows SAVE20 applied, but total remains wrong.")
                    .multilineTextAlignment(.center)

                Text("Subtotal: \(dollars(scenario.subtotalCents))")
                Text("Expected total with \(scenario.couponCode): \(dollars(scenario.expectedTotalCents))")
                Text("Coupon shown in UI: \(displayedCouponCode ?? "none")")

                if let latestQuote {
                    Text("Actual total: \(dollars(latestQuote.totalCents))")
                        .foregroundColor(latestQuote.totalCents == scenario.expectedTotalCents ? .green : .red)
                }

                if let bugClassification {
                    Text("Bug classification: \(bugClassification)")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }

                Button("Apply SAVE20 (Buggy)") {
                    runCheckoutBugScenario()
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

    private func runCheckoutBugScenario() {
        contextStore.selectCoupon(scenario.couponCode)
        displayedCouponCode = contextStore.current.pendingCouponCode

        BreadcrumbStore.shared.add(
            "Tapped apply coupon, uiCoupon=\(displayedCouponCode ?? "none"), subtotalCents=\(scenario.subtotalCents)",
            category: "action"
        )

        BreadcrumbStore.shared.add(
            "Coupon selection updated: pendingCoupon=\(contextStore.current.pendingCouponCode ?? "nil"), appliedCoupon=\(contextStore.current.appliedCouponCode ?? "nil")",
            category: "context"
        )

        let quote = checkoutUseCase.makeQuote(subtotalCents: scenario.subtotalCents)
        latestQuote = quote

        BreadcrumbStore.shared.add(
            "Pricing policy used: couponCode=\(quote.policyCouponCode ?? "nil"), discountPercent=\(quote.policyDiscountPercent)",
            category: "pipeline"
        )

        BreadcrumbStore.shared.add(
            "Engine result: discountCents=\(quote.discountCents), totalCents=\(quote.totalCents)",
            category: "pipeline"
        )

        BreadcrumbStore.shared.add(
            "Triage UI check: expectedUiCoupon=\(scenario.couponCode), displayedCoupon=\(displayedCouponCode ?? "none")",
            category: "triage"
        )

        BreadcrumbStore.shared.add(
            "Triage math check: policyDiscountPercent=\(quote.policyDiscountPercent), expectedDiscountPercent=\(scenario.expectedDiscountPercent), expectedDiscountCents=\(scenario.expectedDiscountCents), actualDiscountCents=\(quote.discountCents)",
            category: "triage"
        )

        BreadcrumbStore.shared.add(
            "Triage policy check: pendingCoupon=\(quote.pendingCouponCode ?? "nil"), appliedCoupon=\(quote.appliedCouponCode ?? "nil"), policyCoupon=\(quote.policyCouponCode ?? "nil")",
            category: "triage"
        )

        let classification = classifyBug(from: quote)
        bugClassification = classification

        if quote.totalCents != scenario.expectedTotalCents {
            BreadcrumbStore.shared.add(
                "Bug observed: class=\(classification), expectedTotalCents=\(scenario.expectedTotalCents), actualTotalCents=\(quote.totalCents)",
                category: "bug"
            )

            DebugReportDraftStore.shared.stage(
                DebugReportDraft(
                    title: "Coupon appears applied but total is unchanged",
                    expectedBehavior: "After applying \(scenario.couponCode), \(dollars(scenario.subtotalCents)) should become \(dollars(scenario.expectedTotalCents)).",
                    actualBehavior: "UI shows coupon \(displayedCouponCode ?? "none"), but total is \(dollars(quote.totalCents)).",
                    reporterNotes: "Classification=\(classification). PendingCoupon=\(quote.pendingCouponCode ?? "nil"), AppliedCoupon=\(quote.appliedCouponCode ?? "nil"), PolicyCoupon=\(quote.policyCouponCode ?? "nil"), PolicyDiscount=\(quote.policyDiscountPercent)%.",
                    screenName: "DemoHome"
                )
            )
        }
    }

    private func classifyBug(from quote: CheckoutQuote) -> String {
        if displayedCouponCode != scenario.couponCode {
            return "ui-only"
        }

        if quote.policyDiscountPercent == scenario.expectedDiscountPercent &&
            quote.discountCents != scenario.expectedDiscountCents {
            return "pricing-math"
        }

        if quote.pendingCouponCode == scenario.couponCode &&
            quote.appliedCouponCode != scenario.couponCode &&
            quote.policyCouponCode != scenario.couponCode {
            return "source-of-truth-policy-application"
        }

        return "unknown"
    }

    private func dollars(_ cents: Int) -> String {
        String(format: "$%.2f", Double(cents) / 100.0)
    }
}

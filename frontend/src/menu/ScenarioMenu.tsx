import type { Scenario } from '../api'
import { SCENARIO_HASH_PREFIX } from '../config'

interface ScenarioMenuProps {
  readonly scenarios: readonly Scenario[]
  /** Why the scenarios could not be loaded, or null. */
  readonly error: string | null
  /** True when the URL named a scenario that does not exist. */
  readonly unknownScenario: boolean
  readonly onRetry: () => void
}

/** Link target that opens a scenario's stage. */
function scenarioHref(scenarioId: string): string {
  if (scenarioId === '') throw new Error('scenarioId is required')
  return `${SCENARIO_HASH_PREFIX}${encodeURIComponent(scenarioId)}`
}

/** One scenario card: name, window and the band it brings to the stage. */
function ScenarioCard({ scenario }: { readonly scenario: Scenario }) {
  return (
    <a className="scenario-card" href={scenarioHref(scenario.id)}>
      <span className="scenario-card__text">
        <h2>{scenario.name}</h2>
        <span className="scenario-card__meta">
          {scenario.period} · {scenario.tickers.join(' ')}
        </span>
      </span>
      <span className="scenario-card__arrow" aria-hidden="true">
        ↗
      </span>
    </a>
  )
}

/** The start screen: pick a historical event, then build its band on the stage. */
export function ScenarioMenu({ scenarios, error, unknownScenario, onRetry }: ScenarioMenuProps) {
  return (
    <main className="scenario-menu">
      <header className="scenario-menu__header">
        <span className="brand">
          <span className="brand__mark" aria-hidden="true">
            ◉
          </span>
          MARKET BAND
        </span>
        <h1>Choose a scenario</h1>
      </header>
      <section aria-label="Scenarios" className="scenario-grid">
        {scenarios.map((scenario) => (
          <ScenarioCard key={scenario.id} scenario={scenario} />
        ))}
      </section>
      {scenarios.length === 0 && error === null && <p role="status">Loading scenarios…</p>}
      {unknownScenario && <p role="alert">That scenario isn’t available. Choose one above.</p>}
      {error !== null && (
        <div role="alert" className="scenario-menu__error">
          <p>Could not load the scenarios. Check that the backend is running.</p>
          <p>{error}</p>
          <button type="button" onClick={onRetry}>
            Try again
          </button>
        </div>
      )}
    </main>
  )
}

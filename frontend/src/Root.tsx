import { useEffect, useState } from 'react'
import { fetchScenarios, type Scenario } from './api'
import App from './App'
import { SCENARIO_HASH_PREFIX } from './config'
import { ScenarioMenu } from './menu/ScenarioMenu'
import './menu/menu.css'

/** The scenario id named by a URL hash, or '' when the hash names none (show the menu). */
function scenarioIdFromHash(hash: string): string {
  if (!hash.startsWith(SCENARIO_HASH_PREFIX)) return ''
  const raw = hash.slice(SCENARIO_HASH_PREFIX.length)
  try {
    return decodeURIComponent(raw)
  } catch {
    return raw // malformed escape: treat as an id that won't match any scenario
  }
}

/** Track `window.location.hash`, so browser Back returns from a scenario to the menu. */
function useHash(): string {
  const [hash, setHash] = useState(window.location.hash)
  useEffect(() => {
    const update = (): void => setHash(window.location.hash)
    window.addEventListener('hashchange', update)
    return () => window.removeEventListener('hashchange', update)
  }, [])
  return hash
}

/** Top level: the scenario menu, or the stage for the scenario named in the URL hash. */
export default function Root() {
  const [scenarios, setScenarios] = useState<Scenario[]>([])
  const [error, setError] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)
  const hash = useHash()

  useEffect(() => {
    let cancelled = false
    fetchScenarios()
      .then((loaded) => {
        if (!cancelled) setScenarios(loaded)
      })
      .catch((reason: unknown) => {
        if (!cancelled) setError(String(reason))
      })
    return () => {
      cancelled = true
    }
  }, [attempt])

  const retry = (): void => {
    setError(null)
    setAttempt((value) => value + 1)
  }

  const scenarioId = scenarioIdFromHash(hash)
  const selected = scenarios.find((scenario) => scenario.id === scenarioId)
  // key: a new scenario gets a fresh stage (band, assignments, playhead), never a reused one.
  if (selected !== undefined) return <App key={selected.id} scenario={selected} />
  return (
    <ScenarioMenu
      scenarios={scenarios}
      error={error}
      unknownScenario={scenarioId !== '' && scenarios.length > 0}
      onRetry={retry}
    />
  )
}

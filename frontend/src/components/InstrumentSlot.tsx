import { useState, type DragEvent } from 'react'
import { midiUrl, type Dataset, type Instrument, type IRSeries } from '../api'
import { DRAG_MIME } from '../config'
import { LevelChart } from './LevelChart'

interface InstrumentSlotProps {
  readonly instrument: Instrument
  readonly dataset: Dataset | null
  readonly ir: IRSeries | null
  readonly beat: number | null
  readonly onAssign: (instrumentId: string, datasetId: string) => void
  readonly onClear: (instrumentId: string) => void
}

/** A band member on stage: a drop target for datasets, showing what it is playing. */
export function InstrumentSlot(props: InstrumentSlotProps) {
  const { instrument, dataset, ir, beat, onAssign, onClear } = props
  const [hovering, setHovering] = useState(false)

  const handleDragOver = (event: DragEvent<HTMLDivElement>): void => {
    if (!event.dataTransfer.types.includes(DRAG_MIME)) return
    event.preventDefault()
    setHovering(true)
  }

  const handleDrop = (event: DragEvent<HTMLDivElement>): void => {
    event.preventDefault()
    setHovering(false)
    const datasetId = event.dataTransfer.getData(DRAG_MIME)
    if (datasetId === '') return
    onAssign(instrument.id, datasetId)
  }

  return (
    <div
      className={`slot${hovering ? ' slot--hover' : ''}${dataset ? ' slot--filled' : ''}`}
      onDragOver={handleDragOver}
      onDragLeave={() => setHovering(false)}
      onDrop={handleDrop}
    >
      <header className="slot__header">
        <h3>{instrument.name}</h3>
        {dataset && (
          <span className="slot__actions">
            <a href={midiUrl(dataset.id, instrument.id)} download>
              .mid
            </a>
            <button type="button" onClick={() => onClear(instrument.id)} aria-label="Remove">
              ×
            </button>
          </span>
        )}
      </header>
      {dataset ? (
        <>
          <p className="slot__dataset">
            {dataset.ticker} <span>{dataset.name}</span>
          </p>
          {ir && <LevelChart ir={ir} beat={beat} />}
        </>
      ) : (
        <p className="slot__empty">Drop a dataset here</p>
      )}
    </div>
  )
}

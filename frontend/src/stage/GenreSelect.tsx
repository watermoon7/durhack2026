import type { ChangeEvent } from 'react'
import type { Genre } from '../api'

interface GenreSelectProps {
  readonly genres: readonly Genre[]
  readonly value: string
  readonly onChange: (genre: string) => void
}

/** The genre dropdown, top-left over the stage. A native select, so it works from the keyboard. */
export function GenreSelect({ genres, value, onChange }: GenreSelectProps) {
  if (genres.length > 0 && !genres.some((genre) => genre.id === value)) {
    throw new Error(`selected genre '${value}' is not in the list`)
  }
  const handleChange = (event: ChangeEvent<HTMLSelectElement>): void => onChange(event.target.value)
  return (
    <label className="genre">
      <span className="genre__label">Genre</span>
      <select className="genre__select" value={value} onChange={handleChange} disabled={genres.length === 0}>
        {genres.map((genre) => (
          <option key={genre.id} value={genre.id}>
            {genre.name}
          </option>
        ))}
      </select>
    </label>
  )
}

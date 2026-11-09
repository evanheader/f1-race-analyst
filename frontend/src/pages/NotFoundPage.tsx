import { Link } from 'react-router'

export default function NotFoundPage() {
  return (
    <div>
      <h1 className="display">Page not found</h1>
      <p className="mt-3 text-muted">
        <Link className="underline decoration-line-strong underline-offset-[3px]" to="/">
          Back to the races
        </Link>
      </p>
    </div>
  )
}

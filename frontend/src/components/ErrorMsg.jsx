import { AlertCircle } from 'lucide-react'

export default function ErrorMsg({ message }) {
  return (
    <div className="flex items-start gap-3 p-4 bg-red-50 border border-red-200 rounded-xl text-sm text-red-700">
      <AlertCircle size={16} className="mt-0.5 shrink-0 text-red-500" />
      <span>{message || 'Something went wrong.'}</span>
    </div>
  )
}

export default function Spinner({ className = '' }) {
  return (
    <div className={`flex items-center justify-center py-12 ${className}`}>
      <div className="w-6 h-6 border-2 border-gray-200 border-t-blue-500 rounded-full animate-spin" />
    </div>
  )
}

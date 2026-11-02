// Лінійні іконки (stroke = currentColor), як у макеті

function Svg({ size = 18, children, strokeWidth = 1.8 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={strokeWidth}
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {children}
    </svg>
  )
}

export const ScaleIcon = (p) => <Svg size={22} {...p}><path d="M12 3v18M5 21h14M6 7h12M6 7l-3 7a3 3 0 0 0 6 0zM18 7l-3 7a3 3 0 0 0 6 0z" /></Svg>
export const TableIcon = (p) => <Svg {...p}><rect x="3" y="4" width="18" height="16" rx="2" /><path d="M3 10h18M9 10v10" /></Svg>
export const CurveIcon = (p) => <Svg {...p}><path d="M4 19c4 0 5-14 9-14s4 9 7 9" /><path d="M4 5v14h16" /></Svg>
export const BookIcon = (p) => <Svg {...p}><path d="M5 4h10a4 4 0 0 1 4 4v12H9a4 4 0 0 1-4-4z" /><path d="M9 8h6M9 12h6" /></Svg>
export const CheckIcon = (p) => <Svg size={16} strokeWidth={2.4} {...p}><path d="M5 12l5 5 9-10" /></Svg>
export const StarIcon = (p) => <Svg size={14} strokeWidth={2} {...p}><path d="M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1L3.2 9.5l6.1-.9z" /></Svg>
export const ArrowIcon = (p) => <Svg size={16} strokeWidth={2} {...p}><path d="M5 12h14M13 6l6 6-6 6" /></Svg>
export const CloseIcon = (p) => <Svg size={14} strokeWidth={2.2} {...p}><path d="M6 6l12 12M18 6L6 18" /></Svg>
export const WarnIcon = (p) => <Svg size={20} strokeWidth={2} {...p}><path d="M12 4l9 16H3z" /><path d="M12 10v4M12 17h.01" /></Svg>
export const OkIcon = (p) => <Svg size={20} strokeWidth={2} {...p}><circle cx="12" cy="12" r="9" /><path d="M8 12l3 3 5-6" /></Svg>
export const UpIcon = (p) => <Svg size={16} strokeWidth={2} {...p}><path d="M6 15l6-6 6 6" /></Svg>
export const DownIcon = (p) => <Svg size={16} strokeWidth={2} {...p}><path d="M6 9l6 6 6-6" /></Svg>
export const LinearIcon = (p) => <Svg size={14} strokeWidth={2.2} {...p}><path d="M4 18L10 8l4 6 6-10" /></Svg>
export const PlusIcon = (p) => <Svg size={16} strokeWidth={2} {...p}><path d="M12 5v14M5 12h14" /></Svg>
export const DownloadIcon = (p) => <Svg size={16} strokeWidth={2} {...p}><path d="M12 4v11M7 10l5 5 5-5M5 20h14" /></Svg>

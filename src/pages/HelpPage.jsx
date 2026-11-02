import { useEffect, useState } from 'react'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { api } from '../api.js'
import { ErrorBox, Loading, PageHead, Segmented } from '../components/ui.jsx'

const DOCS = [{ value: 'user_guide', label: 'Інструкція користувача' }, { value: 'methods', label: 'Опис методів' }]

export default function HelpPage() {
  const [doc, setDoc] = useState('user_guide')
  const [state, setState] = useState({ data: null, error: null })
  useEffect(() => {
    let alive = true
    api.doc(doc).then((data) => alive && setState({ data, error: null })).catch((error) => alive && setState({ data: null, error }))
    return () => {
      alive = false
    }
  }, [doc])
  return (
    <>
      <PageHead eyebrow="Довідка" title="Як користуватися MCO">
        <Segmented label="Документ" value={doc} onChange={setDoc} options={DOCS} />
      </PageHead>
      <ErrorBox error={state.error} />
      <article className="card markdown" style={{ maxWidth: 960 }}>
        {state.data && state.data.id === doc ? <Markdown remarkPlugins={[remarkGfm]}>{state.data.markdown}</Markdown> : !state.error && <Loading>Завантажую…</Loading>}
      </article>
    </>
  )
}

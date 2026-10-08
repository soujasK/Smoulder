import { lazy, Suspense, useEffect } from 'react';
import { Route, Routes, useLocation, useSearchParams } from 'react-router-dom';
import { Footer, Loading, Masthead, StatusBanner } from './components/Chrome';
import { useSnapshot } from './data/snapshot';
import { useLang } from './i18n';
import { Home } from './screens/Home';
// Routes other than the home screen load on demand (MapLibre only ships with the Atlas).
const Atlas = lazy(() => import('./screens/Atlas').then((m) => ({ default: m.Atlas })));
const SiteSheet = lazy(() => import('./screens/SiteSheet').then((m) => ({ default: m.SiteSheet })));
const Method = lazy(() => import('./screens/Method').then((m) => ({ default: m.Method })));
const Pipeline = lazy(() => import('./screens/Pipeline').then((m) => ({ default: m.Pipeline })));
const PrintSite = lazy(() => import('./screens/Print').then((m) => ({ default: m.PrintSite })));
const PrintSmoke = lazy(() => import('./screens/Print').then((m) => ({ default: m.PrintSmoke })));

export default function App() {
  const snap = useSnapshot();
  const loc = useLocation();
  const [params] = useSearchParams();
  const lang = useLang((s) => s.lang);
  const demo = params.get('demo') === '1';
  const print = loc.pathname.startsWith('/print');
  useEffect(() => { document.documentElement.lang = lang; }, [lang]);
  useEffect(() => { if (!loc.hash) window.scrollTo(0, 0); }, [loc.pathname, loc.hash]);

  if (snap.isError) {
    return (
      <main className="page" style={{ paddingTop: 48 }}>
        <p className="serif" style={{ fontSize: 28 }}>The data snapshot could not be loaded.</p>
        <p className="muted">{String(snap.error)}</p>
      </main>
    );
  }
  return (
    <>
      {!print && <Masthead />}
      {!print && !demo && <StatusBanner />}
      {snap.isLoading ? <Loading /> : (
        <Suspense fallback={<Loading />}>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/sites" element={<Atlas />} />
          <Route path="/site/:id" element={<SiteSheet />} />
          <Route path="/method" element={<Method />} />
          <Route path="/pipeline" element={<Pipeline />} />
          <Route path="/print/site/:id" element={<PrintSite />} />
          <Route path="/print/smoke" element={<PrintSmoke />} />
          <Route path="*" element={<main className="page" style={{ paddingTop: 48 }}><p>Not found.</p></main>} />
        </Routes>
        </Suspense>
      )}
      {!print && !demo && <Footer />}
    </>
  );
}

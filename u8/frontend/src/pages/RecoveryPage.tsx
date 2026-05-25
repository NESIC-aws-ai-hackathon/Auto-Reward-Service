import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { useApi } from '../hooks/useApi';
import './RecoveryPage.css';

interface RecoveryItem {
  id: string;
  text: string;
  category: string;
  budget_hint?: string;
}

interface RecoveryData {
  stress_level: number | null;
  mood: string | null;
  free_recovery: RecoveryItem[];
  paid_recovery: RecoveryItem[];
  message: string;
}

interface WishlistItem {
  wishlist_item_id: string;
  product_title: string;
  product_url: string;
  product_image_url: string;
  price?: number;
  desire_aging_days?: number;
}

interface ProductItem {
  name: string;
  price: number;
  url: string;
  image: string;
  shop: string;
}

interface VideoItem {
  title: string;
  channel: string;
  url: string;
  thumbnail: string;
}

export function RecoveryPage() {
  const api = useApi();
  const [data, setData] = useState<RecoveryData | null>(null);
  const [loading, setLoading] = useState(true);
  const [permitDone, setPermitDone] = useState<Set<string>>(new Set());
  const [routeStarted, setRouteStarted] = useState(false);
  const [routeStep, setRouteStep] = useState(0);

  const fetchData = useCallback(async () => {
    try {
      const result = await api.getRecovery();
      setData(result);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, [api]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handlePermit = async (item: RecoveryItem, type: string) => {
    try {
      await api.recordPermit(item.id, type);
      setPermitDone(prev => new Set(prev).add(item.id));
    } catch { /* ignore */ }
  };

  const handleSkip = async () => {
    try { await api.recordSkip('今日はいいかな'); } catch { /* ignore */ }
  };

  const heroMessage = data?.message || 'つかれた日は、甘いプリンでほっと一息っこ?';
  const freeItems = data?.free_recovery || [];
  const paidItems = data?.paid_recovery || [];

  const routeSteps = [
    { emoji: '☁️', label: '深呼吸', time: '1分' },
    { emoji: '🍵', label: 'あたたかい飲み物', time: '5分' },
    { emoji: '🎵', label: 'やさしい音楽', time: '10分' },
    { emoji: '💗', label: '自分をほめる', time: '3分' },
  ];

  const handleRouteStart = () => {
    setRouteStarted(true);
    setRouteStep(0);
  };

  const handleRouteNext = () => {
    if (routeStep < routeSteps.length - 1) {
      setRouteStep(routeStep + 1);
    } else {
      setRouteStarted(false);
      setRouteStep(0);
    }
  };

  return (
    <div className="page-content">
      {/* Recovery Hero */}
      <section className="recovery-hero">
        <img src="/assets/furemaru-happy.png" alt="ふれまーるちゃん" />
        <div>
          <small>{data?.mood ? `今の気分: ${data.mood}` : 'おすすめの回復を提案するよ♪'}</small>
          <h2>{heroMessage}</h2>
          <p>心がふわっとゆるむよ〜🌿</p>
          <button className="primary-btn" onClick={handleSkip}>今日はいいかな</button>
          <Link to="/" className="chat-back-link">💬 ふれまーるちゃんと話す</Link>
        </div>
      </section>

      {/* 0円回復 */}
      {freeItems.length > 0 && (
        <>
          <h2 className="section-heading">🌿 0円回復メニュー</h2>
          <section className="recovery-grid">
            {freeItems.map(item => (
              <article key={item.id} className={permitDone.has(item.id) ? 'done' : ''}>
                <span>{item.category === '呼吸' ? '☁️' : item.category === '運動' ? '🚶' : item.category === '音楽' ? '🎵' : '🌿'}</span>
                <h3>{item.text}</h3>
                <p>{item.category}</p>
                {!permitDone.has(item.id) ? (
                  <button className="primary-btn small" onClick={() => handlePermit(item, 'free')}>やってみる</button>
                ) : (
                  <p className="done-text">✅ やったよ！</p>
                )}
              </article>
            ))}
          </section>
        </>
      )}

      {/* 有料回復 */}
      {paidItems.length > 0 && (
        <>
          <h2 className="section-heading">💗 小さなご褒美</h2>
          <section className="recovery-grid">
            {paidItems.map(item => (
              <article key={item.id} className={permitDone.has(item.id) ? 'done' : ''}>
                <span>🍮</span>
                <h3>{item.text}</h3>
                <p>{item.category}{item.budget_hint ? ` (${item.budget_hint})` : ''}</p>
                {!permitDone.has(item.id) ? (
                  <button className="primary-btn small" onClick={() => handlePermit(item, 'paid')}>買ってもいい？</button>
                ) : (
                  <p className="done-text">✅ 許可しました♪</p>
                )}
              </article>
            ))}
          </section>
        </>
      )}

      {/* データなし時のフォールバック */}
      {!loading && freeItems.length === 0 && paidItems.length === 0 && (
        <>
          <h2 className="section-heading">🌿 かんたん回復メニュー</h2>
          <section className="recovery-grid">
            <article>
              <span>👛</span>
              <h3>0円回復</h3>
              <p>チャットで「疲れた」と話しかけると、あなたに合った回復案が表示されるよ♪</p>
            </article>
            <article>
              <span>💗</span>
              <h3>小さなご褒美</h3>
              <p>がんばった自分にやさしいごほうびをプレゼント♪</p>
            </article>
          </section>
        </>
      )}

      {/* Route Card */}
      <section className="route-card">
        <h2>今日の回復ルート</h2>
        <div className="route">
          {routeSteps.map((step, i) => (
            <span key={i}>
              <div className={`step${routeStarted && i === routeStep ? ' current' : ''}${routeStarted && i < routeStep ? ' completed' : ''}`}>
                {step.emoji}<small>{step.label}<br />{step.time}</small>
              </div>
              {i < routeSteps.length - 1 && <div className="connector"></div>}
            </span>
          ))}
          <div className="total">合計<br />19分</div>
        </div>
        {!routeStarted ? (
          <button className="start-btn" onClick={handleRouteStart}>はじめる</button>
        ) : (
          <button className="start-btn" onClick={handleRouteNext}>
            {routeStep < routeSteps.length - 1 ? '次のステップへ →' : '完了！おつかれさま 🎉'}
          </button>
        )}
        <p className="route-footer">今日も、あなたのペースで大丈夫だよ〜🌿</p>
      </section>

      {loading && <div className="loading-state">読み込み中...</div>}

      {/* 実データ統合：Wishlist / 楽天 / YouTube */}
      <RecoveryIntegrations mood={data?.mood || ''} />
    </div>
  );
}

function RecoveryIntegrations({ mood }: { mood: string }) {
  const api = useApi();
  const [tab, setTab] = useState<'wishlist' | 'rakuten' | 'youtube'>('wishlist');
  const [wishlist, setWishlist] = useState<WishlistItem[] | null>(null);
  const [products, setProducts] = useState<ProductItem[] | null>(null);
  const [videos, setVideos] = useState<VideoItem[] | null>(null);
  const [loading, setLoading] = useState(false);

  // 気分キーワードマッピング
  const keyword = (() => {
    const m = mood || '';
    if (m.includes('疲') || m.includes('しんど')) return '癒し';
    if (m.includes('ストレス') || m.includes('イラ')) return 'リラックス';
    if (m.includes('楽し')) return 'ごしょうび';
    return 'リラックス';
  })();

  const loadWishlist = useCallback(async () => {
    if (wishlist !== null) return;
    setLoading(true);
    try {
      const r = await api.getWishlistItems('ACTIVE');
      setWishlist(r.items || []);
    } catch { setWishlist([]); }
    finally { setLoading(false); }
  }, [api, wishlist]);

  const loadProducts = useCallback(async () => {
    if (products !== null) return;
    setLoading(true);
    try {
      const r = await api.searchProducts(keyword, undefined, 3000);
      setProducts(r.products || []);
    } catch { setProducts([]); }
    finally { setLoading(false); }
  }, [api, products, keyword]);

  const loadVideos = useCallback(async () => {
    if (videos !== null) return;
    setLoading(true);
    try {
      const r = await api.searchYoutube(keyword);
      setVideos(r.videos || []);
    } catch { setVideos([]); }
    finally { setLoading(false); }
  }, [api, videos, keyword]);

  useEffect(() => {
    if (tab === 'wishlist') loadWishlist();
    else if (tab === 'rakuten') loadProducts();
    else if (tab === 'youtube') loadVideos();
  }, [tab, loadWishlist, loadProducts, loadVideos]);

  const tabs: { key: typeof tab; label: string; icon: string }[] = [
    { key: 'wishlist', label: 'ほしいもの', icon: '💝' },
    { key: 'rakuten', label: '楽天で探す', icon: '🛍️' },
    { key: 'youtube', label: '癒し動画', icon: '🎧' },
  ];

  return (
    <section className="chart-card" style={{ padding: 16, marginTop: 16 }}>
      <h2 style={{ marginTop: 0 }}>✨ 実際のご褐美・癒し</h2>
      <p style={{ fontSize: 11, color: '#8e8270', margin: '4px 0 12px' }}>
        「{keyword}」でおすすめを探したよ🌱
      </p>
      <div style={{ display: 'flex', gap: 6, marginBottom: 12 }}>
        {tabs.map(t => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            style={{
              flex: 1,
              padding: '8px 4px',
              border: '1px solid #e3dac1',
              background: tab === t.key ? '#f4b8b8' : '#fff',
              color: tab === t.key ? '#fff' : '#4a4135',
              borderRadius: 10,
              cursor: 'pointer',
              fontSize: 12,
              fontWeight: tab === t.key ? 'bold' : 'normal',
            }}
          >{t.icon} {t.label}</button>
        ))}
      </div>

      {loading && <p style={{ fontSize: 12, color: '#8e8270', textAlign: 'center', padding: 12 }}>探してるよ～</p>}

      {tab === 'wishlist' && !loading && (
        wishlist && wishlist.length > 0 ? (
          <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'grid', gap: 8 }}>
            {wishlist.slice(0, 6).map(it => (
              <li key={it.wishlist_item_id} style={{ display: 'flex', gap: 10, padding: 8, background: '#fffdf6', borderRadius: 10 }}>
                {it.product_image_url && <img src={it.product_image_url} alt="" style={{ width: 56, height: 56, objectFit: 'cover', borderRadius: 8, background: '#f0e8d8' }} />}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <a href={it.product_url} target="_blank" rel="noopener noreferrer" style={{ fontSize: 12, fontWeight: 'bold', color: '#4a4135', textDecoration: 'none', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                    {it.product_title}
                  </a>
                  <div style={{ fontSize: 11, color: '#7fa05f', marginTop: 4 }}>
                    {it.price ? `¥${it.price.toLocaleString()}` : ''}
                    {it.desire_aging_days ? <span style={{ marginLeft: 8, color: '#a69c8c' }}>欲しくなって{it.desire_aging_days}日</span> : null}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <p style={{ fontSize: 12, color: '#a69c8c', textAlign: 'center', padding: 16 }}>
            ほしいものリストがまだ登録されてないよ。<br />
            <Link to="/settings" style={{ color: '#7fa05f' }}>設定から公開URLを登録</Link>してみてね♪
          </p>
        )
      )}

      {tab === 'rakuten' && !loading && (
        products && products.length > 0 ? (
          <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'grid', gap: 8 }}>
            {products.slice(0, 6).map((p, i) => (
              <li key={i} style={{ display: 'flex', gap: 10, padding: 8, background: '#fffdf6', borderRadius: 10 }}>
                {p.image && <img src={p.image} alt="" style={{ width: 56, height: 56, objectFit: 'cover', borderRadius: 8, background: '#f0e8d8' }} />}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <a href={p.url} target="_blank" rel="noopener noreferrer" style={{ fontSize: 12, fontWeight: 'bold', color: '#4a4135', textDecoration: 'none', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                    {p.name}
                  </a>
                  <div style={{ fontSize: 11, color: '#7fa05f', marginTop: 4 }}>
                    ¥{p.price.toLocaleString()} <span style={{ color: '#a69c8c', marginLeft: 6 }}>{p.shop}</span>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <p style={{ fontSize: 12, color: '#a69c8c', textAlign: 'center', padding: 16 }}>見つからなかったよ。ちょっと後で試してみて～</p>
        )
      )}

      {tab === 'youtube' && !loading && (
        videos && videos.length > 0 ? (
          <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'grid', gap: 8 }}>
            {videos.slice(0, 6).map((v, i) => (
              <li key={i} style={{ display: 'flex', gap: 10, padding: 8, background: '#fffdf6', borderRadius: 10 }}>
                {v.thumbnail && <img src={v.thumbnail} alt="" style={{ width: 80, height: 56, objectFit: 'cover', borderRadius: 8, background: '#f0e8d8' }} />}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <a href={v.url} target="_blank" rel="noopener noreferrer" style={{ fontSize: 12, fontWeight: 'bold', color: '#4a4135', textDecoration: 'none', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                    {v.title}
                  </a>
                  <div style={{ fontSize: 11, color: '#a69c8c', marginTop: 4 }}>{v.channel}</div>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <p style={{ fontSize: 12, color: '#a69c8c', textAlign: 'center', padding: 16 }}>動画が見つからなかったよ。</p>
        )
      )}
    </section>
  );
}

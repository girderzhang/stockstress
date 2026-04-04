import os
import json
import hashlib
from datetime import datetime, timedelta
import akshare as ak
import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score
from scipy.signal import argrelextrema
import warnings
warnings.filterwarnings('ignore')

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import io
import base64
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

app = Flask(__name__)
app.secret_key = 'stock-analyzer-secret-key-2024'

USERS_FILE = 'users.json'
MACHINES_FILE = 'machines.json'

def init_users():
    if not os.path.exists(USERS_FILE):
        users = [
            {
                'username': 'girder',
                'password_hash': hash_password('56707763'),
                'expiry_date': None,
                'remark': '超级管理员',
                'is_admin': True,
                'created_at': datetime.now().isoformat()
            },
            {
                'username': 'guest',
                'password_hash': hash_password('guest'),
                'expiry_date': None,
                'remark': '访客用户',
                'is_admin': False,
                'created_at': datetime.now().isoformat()
            }
        ]
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(users, f, ensure_ascii=False, indent=2)

def load_machines():
    if os.path.exists(MACHINES_FILE):
        with open(MACHINES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_machines(machines):
    with open(MACHINES_FILE, 'w', encoding='utf-8') as f:
        json.dump(machines, f, ensure_ascii=False, indent=2)

def get_machine_id():
    user_agent = request.headers.get('User-Agent', '')
    ip = request.remote_addr or 'unknown'
    machine_str = f"{ip}-{user_agent}"
    return hashlib.sha256(machine_str.encode()).hexdigest()

def is_machine_valid(machine_id, username):
    machines = load_machines()
    if username not in machines:
        return False
    if machine_id not in machines[username]:
        return False
    machine_info = machines[username][machine_id]
    expiry = datetime.fromisoformat(machine_info['expiry_date'])
    return datetime.now() <= expiry

def register_machine(machine_id, username):
    machines = load_machines()
    if username not in machines:
        machines[username] = {}
    expiry_date = (datetime.now() + timedelta(days=7)).isoformat()
    machines[username][machine_id] = {
        'expiry_date': expiry_date,
        'registered_at': datetime.now().isoformat(),
        'user_agent': request.headers.get('User-Agent', ''),
        'ip': request.remote_addr or 'unknown'
    }
    save_machines(machines)

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_users(users):
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def is_user_valid(user):
    if user.get('is_admin'):
        return True
    if not user.get('expiry_date'):
        return True
    expiry = datetime.fromisoformat(user['expiry_date'])
    return datetime.now() <= expiry

matplotlib.rcParams["font.family"] = ["SimHei", "WenQuanYi Micro Hei", "Heiti TC"]
matplotlib.rcParams['font.size'] = 12
matplotlib.rcParams['axes.titlesize'] = 14
matplotlib.rcParams['axes.labelsize'] = 12
matplotlib.rcParams['xtick.labelsize'] = 10
matplotlib.rcParams['ytick.labelsize'] = 10
matplotlib.rcParams['legend.fontsize'] = 10

class StockAnalyzer:
    def find_significant_extremes(self, df, window=5):
        if 'high' not in df.columns or 'low' not in df.columns:
            df['high'] = df['close']
            df['low'] = df['close']
        
        highs = df['high'].rolling(window=window, center=True).max()
        lows = df['low'].rolling(window=window, center=True).min()
        
        peak_condition = (df['high'] == highs) & (df['high'] > df['high'].shift(window))
        trough_condition = (df['low'] == lows) & (df['low'] < df['low'].shift(window))
        
        peaks = df[peak_condition]['high']
        troughs = df[trough_condition]['low']
        
        return peaks, troughs

    def create_clustering_features(self, df, peaks, troughs):
        features = []
        price_data = []
        
        for price in peaks:
            matching_days = df[df['high'] == price]
            if not matching_days.empty:
                volume_weight = matching_days['volume'].mean()
                price_tolerance = price * 0.01
                frequency = len(df[(df['high'] >= price - price_tolerance) & 
                                 (df['high'] <= price + price_tolerance)])
                
                features.append([price, volume_weight, frequency])
                price_data.append(price)
        
        for price in troughs:
            matching_days = df[df['low'] == price]
            if not matching_days.empty:
                volume_weight = matching_days['volume'].mean()
                price_tolerance = price * 0.01
                frequency = len(df[(df['low'] >= price - price_tolerance) & 
                                 (df['low'] <= price + price_tolerance)])
                
                features.append([price, volume_weight, frequency])
                price_data.append(price)
        
        if not features:
            all_prices = list(peaks) + list(troughs)
            features = [[price, 1, 1] for price in all_prices]
            price_data = all_prices
        
        return np.array(features), price_data

    def calculate_support_resistance(self, centers, current_price, df, threshold_ratio=5):
        if len(centers) == 0:
            return None, None, [], []
        
        sorted_centers = sorted(centers)
        price_range = df['high'].max() - df['low'].min()
        threshold = price_range * (threshold_ratio / 100)
        
        supports = [c for c in sorted_centers if c < current_price and (current_price - c) <= threshold]
        resistances = [c for c in sorted_centers if c > current_price and (c - current_price) <= threshold]
        
        main_support = max(supports) if supports else (min(sorted_centers) if min(sorted_centers) < current_price else None)
        main_resistance = min(resistances) if resistances else (max(sorted_centers) if max(sorted_centers) > current_price else None)
        
        secondary_supports = [c for c in sorted_centers if c < current_price and c != main_support]
        secondary_resistances = [c for c in sorted_centers if c > current_price and c != main_resistance]
        
        return main_support, main_resistance, secondary_supports, secondary_resistances

    def calculate_technical_indicators(self, df):
        try:
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            
            bb_middle = df['close'].rolling(20).mean()
            bb_std = df['close'].rolling(20).std()
            bb_upper = bb_middle + 2 * bb_std
            bb_lower = bb_middle - 2 * bb_std
            
            exp12 = df['close'].ewm(span=12, adjust=False).mean()
            exp26 = df['close'].ewm(span=26, adjust=False).mean()
            macd = exp12 - exp26
            signal = macd.ewm(span=9, adjust=False).mean()
            histogram = macd - signal
            
            return {
                'rsi': rsi,
                'bb_upper': bb_upper,
                'bb_middle': bb_middle,
                'bb_lower': bb_lower,
                'macd': macd,
                'macd_signal': signal,
                'macd_histogram': histogram
            }
        except Exception:
            return None

    def validate_with_technical_indicators(self, df, support, resistance, indicators):
        if indicators is None:
            return 0.5, 0.5
        
        current_rsi = indicators['rsi'].iloc[-1] if pd.notna(indicators['rsi'].iloc[-1]) else 50
        current_bb_upper = indicators['bb_upper'].iloc[-1]
        current_bb_lower = indicators['bb_lower'].iloc[-1]
        
        support_confidence = 0.5
        resistance_confidence = 0.5
        
        if support and current_rsi < 30:
            support_confidence += 0.2
        if resistance and current_rsi > 70:
            resistance_confidence += 0.2
        
        if support and abs(support - current_bb_lower) / support < 0.02:
            support_confidence += 0.3
        if resistance and abs(resistance - current_bb_upper) / resistance < 0.02:
            resistance_confidence += 0.3
        
        return min(support_confidence, 1.0), min(resistance_confidence, 1.0)

    def backtest_support_resistance(self, df, centers):
        if len(centers) == 0:
            return {}
            
        hit_counts = {center: 0 for center in centers}
        bounce_counts = {center: 0 for center in centers}
        
        for i in range(1, len(df)):
            current_price = df['close'].iloc[i]
            prev_price = df['close'].iloc[i-1]
            
            for center in centers:
                if abs(current_price - center) / center < 0.01:
                    hit_counts[center] += 1
                    if (prev_price < center and current_price > center) or \
                       (prev_price > center and current_price < center):
                        bounce_counts[center] += 1
        
        effectiveness = {}
        for center in centers:
            if hit_counts[center] > 0:
                effectiveness[center] = {
                    'score': bounce_counts[center] / hit_counts[center],
                    'hits': hit_counts[center],
                    'bounces': bounce_counts[center]
                }
            else:
                effectiveness[center] = {
                    'score': 0,
                    'hits': 0,
                    'bounces': 0
                }
        
        return effectiveness

    def calculate_volume_profile(self, df, bins=25):
        try:
            prices = np.concatenate([df['high'].values, df['low'].values, df['close'].values])
            volume = df['volume'].values
            
            price_min = df['low'].min()
            price_max = df['high'].max()
            price_bins = np.linspace(price_min, price_max, bins)
            price_centers = (price_bins[:-1] + price_bins[1:]) / 2
            
            vol_profile = np.zeros(len(price_centers))
            for i in range(len(df)):
                idx = np.digitize([df['low'].iloc[i], df['high'].iloc[i]], price_bins)
                if idx[0] < idx[1]:
                    vol_profile[idx[0]:idx[1]] += volume[i]
            
            poc_idx = np.argmax(vol_profile)
            poc_price = price_centers[poc_idx]
            poc_vol = vol_profile[poc_idx]
            
            total_vol = vol_profile.sum()
            target_vol = total_vol * 0.7
            sorted_idx = np.argsort(vol_profile)[::-1]
            
            cum_vol = 0
            va_indices = []
            for idx in sorted_idx:
                cum_vol += vol_profile[idx]
                va_indices.append(idx)
                if cum_vol >= target_vol:
                    break
            
            va_prices = price_centers[va_indices]
            va_low = va_prices.min()
            va_high = va_prices.max()
            
            vp_levels = [poc_price, va_low, va_high]
            vp_effectiveness = self.backtest_support_resistance(df, vp_levels)
            
            return {
                'price_centers': price_centers,
                'vol_profile': vol_profile,
                'poc_price': poc_price,
                'poc_vol': poc_vol,
                'va_low': va_low,
                'va_high': va_high,
                'total_vol': total_vol,
                'effectiveness': vp_effectiveness
            }
        except Exception:
            return None

    def get_full_stock_code(self, code, market):
        if not code:
            return None
            
        if market == "A股":
            if len(code) == 6 and code.isdigit():
                if code.startswith(('600', '601', '603', '605', '688')):
                    return f"sh{code}"
                elif code.startswith(('000', '001', '002', '003', '300', '301')):
                    return f"sz{code}"
                else:
                    return f"sh{code}"
        else:
            if len(code) == 5 and code.isdigit():
                return f"hk{code}"
        return None

    def analyze(self, stock_code, market="A股", start_date=None, end_date=None, 
                window_size=7, max_clusters=8, threshold_ratio=5, vp_bins=25, adjust="qfq"):
        
        full_code = self.get_full_stock_code(stock_code, market)
        if not full_code:
            return {'error': '股票代码格式错误'}
        
        today = datetime.now()
        one_year_ago = today - timedelta(days=365)
        
        if not start_date:
            start_date = one_year_ago.strftime("%Y%m%d")
        else:
            start_date = start_date.replace('-', '')
        if not end_date:
            end_date = today.strftime("%Y%m%d")
        else:
            end_date = end_date.replace('-', '')
        
        try:
            if market == "A股":
                df = ak.stock_zh_a_daily(
                    symbol=full_code, 
                    start_date=start_date, 
                    end_date=end_date, 
                    adjust=adjust
                )
            else:
                df = ak.stock_hk_daily(
                    symbol=full_code,
                    start_date=start_date,
                    end_date=end_date,
                    parameter="adjusted-price"
                )
                if '收盘' in df.columns:
                    df = df.rename(columns={'收盘': 'close', '日期': 'date', '最高': 'high', '最低': 'low', '成交量': 'volume'})
        except Exception as e:
            return {'error': f'获取数据失败: {str(e)}'}
        
        if df.empty:
            return {'error': '未获取到有效数据'}
        
        if 'date' not in df.columns and '日期' in df.columns:
            df = df.rename(columns={'日期': 'date'})
        if 'close' not in df.columns and '收盘' in df.columns:
            df = df.rename(columns={'收盘': 'close'})
        if 'high' not in df.columns and '最高' in df.columns:
            df = df.rename(columns={'最高': 'high'})
        if 'low' not in df.columns and '最低' in df.columns:
            df = df.rename(columns={'最低': 'low'})
        if 'volume' not in df.columns and '成交量' in df.columns:
            df = df.rename(columns={'成交量': 'volume'})
        
        peaks, troughs = self.find_significant_extremes(df, window_size)
        
        if len(peaks) + len(troughs) < 2:
            return {'error': '有效极值点不足'}
        
        X, price_data = self.create_clustering_features(df, peaks, troughs)
        
        sil_scores = {}
        actual_max_k = min(max_clusters, len(X) // 2)
        if actual_max_k < 2:
            actual_max_k = 2
            
        for k in range(2, actual_max_k + 1):
            km = KMeans(n_clusters=k, random_state=42).fit(X)
            sil_scores[k] = silhouette_score(X, km.labels_)
            
        best_k = max(sil_scores, key=sil_scores.get)
        
        kmeans = KMeans(n_clusters=best_k, random_state=42).fit(X)
        centers = sorted(kmeans.cluster_centers_[:, 0])
        
        indicators = self.calculate_technical_indicators(df)
        
        current_price = df['close'].iloc[-1]
        main_support, main_resistance, secondary_supports, secondary_resistances = self.calculate_support_resistance(
            centers, current_price, df, threshold_ratio
        )
        
        support_confidence, resistance_confidence = self.validate_with_technical_indicators(
            df, main_support, main_resistance, indicators
        )
        
        effectiveness = {}
        if len(df) > 50:
            effectiveness = self.backtest_support_resistance(df, centers)
        
        vp_data = None
        vp_poc = None
        vp_va_low = None
        vp_va_high = None
        if len(df) > 20:
            vp_data = self.calculate_volume_profile(df, vp_bins)
            if vp_data:
                vp_poc = vp_data['poc_price']
                vp_va_low = vp_data['va_low']
                vp_va_high = vp_data['va_high']
        
        result = {
            'stock_code': full_code,
            'current_price': float(current_price),
            'best_k': best_k,
            'centers': [float(c) for c in centers],
            'main_support': float(main_support) if main_support else None,
            'main_resistance': float(main_resistance) if main_resistance else None,
            'secondary_supports': [float(s) for s in secondary_supports],
            'secondary_resistances': [float(r) for r in secondary_resistances],
            'support_confidence': float(support_confidence),
            'resistance_confidence': float(resistance_confidence),
            'effectiveness': {str(k): v for k, v in effectiveness.items()},
            'vp_poc': float(vp_poc) if vp_poc else None,
            'vp_va_low': float(vp_va_low) if vp_va_low else None,
            'vp_va_high': float(vp_va_high) if vp_va_high else None,
            'chart_data': self.generate_chart(df, peaks, troughs, centers, main_support, main_resistance, current_price, indicators, vp_data, best_k, full_code)
        }
        
        return result
    
    def generate_chart(self, df, peaks, troughs, centers, main_support, main_resistance, current_price, indicators, vp_data, best_k, stock_code):
        try:
            fig, ((ax1, ax1_vp), (ax2, ax2_empty)) = plt.subplots(2, 2, figsize=(16, 12), dpi=100, gridspec_kw={'height_ratios': [2, 1], 'width_ratios': [3, 1]})
            
            ax1.plot(df['date'], df['close'], label='收盘价', color='black', linewidth=1, alpha=0.8)
            
            ax1.scatter(df.loc[peaks.index, 'date'], peaks, color='red', s=30, label='局部高点', alpha=0.6)
            ax1.scatter(df.loc[troughs.index, 'date'], troughs, color='blue', s=30, label='局部低点', alpha=0.6)
            
            colors = plt.cm.Set3(np.linspace(0, 1, len(centers)))
            for i, c in enumerate(centers):
                linestyle = '--' if c == main_support or c == main_resistance else ':'
                linewidth = 2 if c == main_support or c == main_resistance else 1
                ax1.axhline(y=c, color=colors[i], linestyle=linestyle, linewidth=linewidth, alpha=0.7,
                           label=f'层级 {i+1}: {c:.2f}')
            
            if main_support:
                ax1.axhline(y=main_support, color='green', linestyle='-', linewidth=2.5, alpha=0.9,
                           label=f'主要支撑 {main_support:.2f}')
            if main_resistance:
                ax1.axhline(y=main_resistance, color='orange', linestyle='-', linewidth=2.5, alpha=0.9,
                           label=f'主要压力 {main_resistance:.2f}')
            
            ax1.axhline(y=current_price, color='red', linestyle='-', linewidth=2, alpha=0.9,
                       label=f'当前价 {current_price:.2f}')
            
            if vp_data:
                ax1.axhline(y=vp_data['poc_price'], color='red', linestyle='-', linewidth=3, alpha=0.8, label=f'POC核心位 {vp_data["poc_price"]:.2f}')
                ax1.axhline(y=vp_data['va_low'], color='forestgreen', linestyle='-.', linewidth=2, alpha=0.7, label=f'VA下沿 {vp_data["va_low"]:.2f}')
                ax1.axhline(y=vp_data['va_high'], color='forestgreen', linestyle='-.', linewidth=2, alpha=0.7, label=f'VA上沿 {vp_data["va_high"]:.2f}')
                ax1.fill_between(df['date'], vp_data['va_low'], vp_data['va_high'], color='green', alpha=0.1, label='价值区域VA')
                
                ax1_vp.barh(vp_data['price_centers'], vp_data['vol_profile'], color='deepskyblue', alpha=0.7, height=(vp_data['price_centers'][1]-vp_data['price_centers'][0])*0.8)
                ax1_vp.axhline(y=vp_data['poc_price'], color='red', linestyle='-', linewidth=2, alpha=0.8)
                ax1_vp.set_title('成交量剖面', fontsize=12)
                ax1_vp.set_xlabel('成交量')
                ax1_vp.grid(alpha=0.2)
            
            ax1.set_title(f"{stock_code} - 支撑位/压力位分析 (K={best_k})【含成交量剖面】", fontsize=14, fontweight='bold')
            ax1.set_ylabel("价格 (元)")
            ax1.legend(loc='upper left', fontsize=8)
            ax1.grid(alpha=0.3)
            
            if indicators is not None and 'rsi' in indicators:
                ax2.plot(df['date'], indicators['rsi'], label='RSI', color='purple', linewidth=1)
                ax2.axhline(y=70, color='red', linestyle='--', alpha=0.7, label='超买线')
                ax2.axhline(y=30, color='green', linestyle='--', alpha=0.7, label='超卖线')
                ax2.set_ylabel("RSI")
                ax2.set_xlabel("交易日期")
                ax2.legend(loc='upper left', fontsize=10)
                ax2.grid(alpha=0.3)
                ax2.set_ylim(0, 100)
            
            ax2_empty.axis('off')
            plt.tight_layout()
            
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
            buf.seek(0)
            chart_base64 = base64.b64encode(buf.read()).decode('utf-8')
            plt.close()
            
            return chart_base64
        except Exception as e:
            print(f"图表生成错误: {str(e)}")
            return None

init_users()
analyzer = StockAnalyzer()

@app.route('/')
def index():
    if 'username' not in session:
        return redirect(url_for('login'))
    users = load_users()
    current_user = next((u for u in users if u['username'] == session['username']), None)
    if not current_user or not is_user_valid(current_user):
        session.pop('username', None)
        return redirect(url_for('login'))
    
    expiry_info = None
    if not current_user.get('is_admin'):
        machine_id = get_machine_id()
        if not is_machine_valid(machine_id, session['username']):
            session.pop('username', None)
            return redirect(url_for('login'))
        machines = load_machines()
        if session['username'] in machines and machine_id in machines[session['username']]:
            expiry_date = datetime.fromisoformat(machines[session['username']][machine_id]['expiry_date'])
            expiry_info = expiry_date.strftime('%Y年%m月%d日 %H:%M:%S')
    
    return render_template('index.html', is_admin=current_user.get('is_admin', False), expiry_info=expiry_info)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        users = load_users()
        user = next((u for u in users if u['username'] == username), None)
        
        if user and user['password_hash'] == hash_password(password) and is_user_valid(user):
            session['username'] = username
            
            if not user.get('is_admin'):
                machine_id = get_machine_id()
                if not is_machine_valid(machine_id, username):
                    register_machine(machine_id, username)
            
            return redirect(url_for('index'))
        
        return render_template('login.html', error='用户名或密码错误，或账号已过期')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/users')
def users_page():
    if 'username' not in session:
        return redirect(url_for('login'))
    users = load_users()
    current_user = next((u for u in users if u['username'] == session['username']), None)
    if not current_user or not current_user.get('is_admin'):
        return redirect(url_for('index'))
    return render_template('users.html', users=users)

@app.route('/api/users', methods=['GET', 'POST', 'DELETE'])
def api_users():
    if 'username' not in session:
        return jsonify({'error': '未登录'}), 401
    users = load_users()
    current_user = next((u for u in users if u['username'] == session['username']), None)
    if not current_user or not current_user.get('is_admin'):
        return jsonify({'error': '无权限'}), 403
    
    if request.method == 'GET':
        return jsonify(users)
    
    if request.method == 'POST':
        data = request.json
        username = data.get('username')
        password = data.get('password')
        expiry_date = data.get('expiry_date')
        remark = data.get('remark', '')
        
        if any(u['username'] == username for u in users):
            return jsonify({'error': '用户名已存在'}), 400
        
        new_user = {
            'username': username,
            'password_hash': hash_password(password),
            'expiry_date': expiry_date if expiry_date else None,
            'remark': remark,
            'is_admin': False,
            'created_at': datetime.now().isoformat()
        }
        users.append(new_user)
        save_users(users)
        return jsonify({'success': True})
    
    if request.method == 'DELETE':
        data = request.json
        username = data.get('username')
        if username == 'girder':
            return jsonify({'error': '不能删除超级管理员'}), 400
        users = [u for u in users if u['username'] != username]
        save_users(users)
        return jsonify({'success': True})

@app.route('/api/analyze', methods=['POST'])
def api_analyze():
    if 'username' not in session:
        return jsonify({'error': '未登录'}), 401
    users = load_users()
    current_user = next((u for u in users if u['username'] == session['username']), None)
    if not current_user or not is_user_valid(current_user):
        return jsonify({'error': '账号已过期'}), 403
    
    if not current_user.get('is_admin'):
        machine_id = get_machine_id()
        if not is_machine_valid(machine_id, session['username']):
            return jsonify({'error': '机器码已过期，请重新登录'}), 403
    
    data = request.json
    stock_code = data.get('stock_code', '600036')
    market = data.get('market', 'A股')
    window_size = int(data.get('window_size', 7))
    max_clusters = int(data.get('max_clusters', 8))
    threshold_ratio = int(data.get('threshold_ratio', 5))
    vp_bins = int(data.get('vp_bins', 25))
    adjust = data.get('adjust', 'qfq')
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    
    result = analyzer.analyze(
        stock_code=stock_code,
        market=market,
        start_date=start_date,
        end_date=end_date,
        window_size=window_size,
        max_clusters=max_clusters,
        threshold_ratio=threshold_ratio,
        vp_bins=vp_bins,
        adjust=adjust
    )
    
    return jsonify(result)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='127.0.0.1', port=port, debug=True)

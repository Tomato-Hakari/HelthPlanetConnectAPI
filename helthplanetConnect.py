import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import sys
import urllib.parse
from dotenv import load_dotenv

load_dotenv()

import os

class FormHandler:
    """HTMLフォームの処理を簡単にするためのクラス"""
    def __init__(self, session, form_element, page_url):
        self.session = session
        self.form = form_element
        self.page_url = page_url
        self.data = {}
        
        # 隠しフィールドを含む全フィールドの初期値を取得
        for input_field in self.form.find_all('input'):
            name = input_field.get('name')
            if name:
                self.data[name] = input_field.get('value', '')
    
    def set_field(self, field_name, value):
        """フォームフィールドに値を設定"""
        self.data[field_name] = value
        
    def click_button(self):
        """フォームを送信してレスポンスを返す"""
        # フォームのアクションURLを取得
        action = self.form.get('action', '')
        if not action.startswith('http'):
            if action.startswith('/'):
                action = f"https://www.healthplanet.jp{action}"
            else:
                base_url = '/'.join(self.page_url.split('/')[:-1])
                action = f"{base_url}/{action}"
        
        # POSTリクエストを送信
        response = self.session.post(
            action,
            data=self.data,
            headers={
                'Referer': self.page_url,
                'Origin': 'https://www.healthplanet.jp'
            },
            allow_redirects=True
        )
        response.raise_for_status()
        return response

class HealthPlanet:
    def __init__(self):
        self.client_id = os.getenv('CLIENT_ID')
        self.client_secret = os.getenv('CLIENT_SECRET')
        self.user_id = os.getenv('USER_ID')
        self.user_pass = os.getenv('USER_PASS')
        self.redirect_uri = os.getenv('REDIRECT_URI')
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8'
        })

    def get_auth_code(self):
        try:
            # 認証ページのURLを正しくエンコード
            auth_params = {
                'client_id': self.client_id,
                'redirect_uri': self.redirect_uri,
                'scope': 'innerscan',
                'response_type': 'code'
            }
            auth_url = "https://www.healthplanet.jp/oauth/auth?" + urllib.parse.urlencode(auth_params)
            # print(f"認証ページにアクセス中: {auth_url}")
            
            # ログインページの取得
            response = self.session.get(auth_url)
            response.raise_for_status()
            
            # ログインフォームの処理
            soup = BeautifulSoup(response.text, 'html.parser')
            login_form = soup.find('form', {'name': 'login.LoginForm'})
            
            if not login_form:
                # print("ページ内容:", response.text[:500])
                raise ValueError("ログインフォームが見つかりません")
            
            # FormHandlerを使用してログイン
            form = FormHandler(self.session, login_form, auth_url)
            form.set_field('loginId', self.user_id)
            form.set_field('passwd', self.user_pass)
            form.set_field('send', '1')
            
            # ログインボタンのクリック
            login_response = form.click_button()
            # print(f"ログイン後のURL: {login_response.url}")
            
            # 承認ページの処理
            approval_soup = BeautifulSoup(login_response.text, 'html.parser')
            approval_form = approval_soup.find('form', {'name': 'common.SiteInfoBaseForm'})
            
            if approval_form:
                # print("承認フォームを検出しました")
                
                # FormHandlerを使用して承認
                approval = FormHandler(self.session, approval_form, login_response.url)
                approval.set_field('approval', 'true')
                
                # 承認ボタンのクリック
                approval_response = approval.click_button()
                # print(f"承認後のURL: {approval_response.url}")
                
                # 最終URLから認証コードを取得
                final_url = approval_response.url
                if 'code=' in final_url:
                    auth_code = final_url.split('code=')[1].split('&')[0]
                    # print(f"認証コード取得成功: {auth_code}")
                    return auth_code
                elif 'error=' in final_url:
                    error = urllib.parse.parse_qs(urllib.parse.urlparse(final_url).query).get('error', ['unknown'])[0]
                    raise ValueError(f"認証に失敗しました。エラー: {error}")
            
            raise ValueError("認証コードを取得できませんでした")
            
        except Exception as e:
            # print(f"エラーが発生しました: {str(e)}")
            raise

    def get_access_token(self, auth_code):
        """認証コードを使用してアクセストークンを取得する"""
        try:
            # トークン取得のためのパラメータを準備
            token_params = {
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'redirect_uri': self.redirect_uri,
                'code': auth_code,
                'grant_type': 'authorization_code'
            }
            
            # トークンエンドポイントにPOSTリクエスト
            token_url = 'https://www.healthplanet.jp/oauth/token'
            # print(f"アクセストークン取得中: {token_url}")
            # print(f"送信パラメータ: {token_params}")
            
            response = self.session.post(
                token_url,
                data=token_params,
                headers={
                    'Content-Type': 'application/x-www-form-urlencoded'
                }
            )
            
            # レスポンスのステータスコードを確認
            response.raise_for_status()
            
            # JSONレスポンスをパース
            try:
                token_data = response.json()
                # print("トークンレスポンス:", token_data)
                
                if 'access_token' in token_data:
                    access_token = token_data['access_token']
                    # print(f"アクセストークン取得成功: {access_token}")
                    return access_token
                else:
                    raise ValueError("レスポンスにアクセストークンが含まれていません")
                    
            except json.JSONDecodeError as e:
                # print(f"JSONパースエラー: {str(e)}")
                # print(f"レスポンス本文: {response.text}")
                raise ValueError("トークンレスポンスの解析に失敗しました")
                
        except requests.exceptions.RequestException as e:
            # print(f"リクエストエラー: {str(e)}")
            raise ValueError(f"トークン取得リクエストに失敗しました: {str(e)}")
            
        except Exception as e:
            # print(f"予期せぬエラー: {str(e)}")
            raise

    def get_scale_data(self, access_token, date_type=1, tag=6021):
        """アクセストークンを使用して重量データを取得する"""
        try:
            # 重量取得のためのパラメータを準備
            scale_params = {
                'access_token': access_token,
                'date_type': date_type,
                'tag': tag
            }
            
            # エンドポイントにPOSTリクエスト
            scale_url = 'https://www.healthplanet.jp/status/innerscan.json'
            # print(f"重量データ取得中: {scale_url}")
            # print(f"送信パラメータ: {scale_params}")
            
            scale_response = self.session.post(
                scale_url,
                data=scale_params
            )
            
            # レスポンスのステータスコードチェック
            scale_response.raise_for_status()
            
            # JSONレスポンスをパース
            try:
                response_data = scale_response.json()
                # print("データレスポンス:", response_data)
                
                if 'data' not in response_data:
                    raise ValueError("APIレスポンスに'data'フィールドが含まれていません")
                
                # print(f"データ取得成功: {len(response_data['data'])}件のデータを取得")
                
                # データの整形
                processed_data = []
                for item in response_data['data']:
                    try:
                        processed_item = {
                            'date': datetime.strptime(item.get('date', ''), '%Y%m%d%H%M'),
                            'keydata': float(item.get('keydata', 0)),
                        }
                        processed_data.append(processed_item)
                    except ValueError as e:
                        # print(f"データ項目の処理中にエラーが発生しました: {str(e)}")
                        continue
                
                return {
                    'raw_data': response_data,
                    'processed_data': processed_data
                }
                
            except json.JSONDecodeError as e:
                # print(f"JSONパースエラー: {str(e)}")
                # print(f"レスポンス本文: {scale_response.text}")
                raise ValueError("データレスポンスの解析に失敗しました")
                
        except requests.exceptions.RequestException as e:
            # print(f"APIリクエストエラー: {str(e)}")
            raise ValueError(f"データ取得リクエストに失敗しました: {str(e)}")
            
        except Exception as e:
            # print(f"予期せぬエラー: {str(e)}")
            raise

def main():
    # print("HealthPlanetデータ取得プログラムを開始します...")
    # print("-" * 50)
    
    hp = HealthPlanet()
    try:
        auth_code = hp.get_auth_code()
        access_token = hp.get_access_token(auth_code)
        scale_data = hp.get_scale_data(access_token)
        
    except Exception as e:
        # print(f"\nエラーが発生しました: {str(e)}")
        sys.exit(1)
    
    return scale_data['processed_data']
    # print(scale_data['raw_data'])
    # for i in range(len(scale_data['processed_data'])):
    #     print(str(i)+"番目："+str(scale_data['processed_data'][i]))
    #     print("\n")
    
    # print("\nプログラムを終了します。")

# if __name__ == "__main__":
#     main()
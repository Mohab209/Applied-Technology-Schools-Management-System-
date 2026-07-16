import os
import streamlit as st
import requests
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="مدارس التكنولوجيا التطبيقية",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# Configuration
# ==========================================
try:
    # Production (Streamlit Cloud)
    API_BASE_URL = st.secrets["API_BASE_URL"]
    SYSTEM_API_KEY = st.secrets["API_KEY"]
except Exception:
    # Local Development
    API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
    SYSTEM_API_KEY = os.getenv("API_KEY")

# تصميم واجهة المستخدم بالـ CSS لتحسين المظهر العربي والاتجاهات دون تخريب الـ Sidebar عند الإغلاق
st.markdown("""
    <style>
    /* تطبيق RTL على الحاوية الرئيسية فقط وتجنب الـ Sidebar */
    .main .block-container {
        direction: rtl;
        text-align: right;
    }
    /* ضمان محاذاة العناوين والنصوص داخل المحتوى الأساسي */
    .main h1, .main h2, .main h3, .main h4, .main p, .main span, .main div {
        direction: rtl;
        text-align: right;
    }
    .stButton>button {
        width: 100%;
    }
    /* تنسيق خاص لزر الحذف لتمييزه */
    .delete-btn button {
        background-color: #ff4b4b !important;
        color: white !important;
        border: none !important;
    }
    .delete-btn button:hover {
        background-color: #ff3333 !important;
        color: white !important;
    }
    </style>
""", unsafe_allow_html=True)

st.title("🎓 نظام إدارة واستعلام مدارس التكنولوجيا التطبيقية")
st.write("نظام ذكي يعتمد على الـ RAG واستخراج البيانات المدعوم بالذكاء الاصطناعي.")

# --- نظام التحقق والمصادقة للإدارة ---
st.sidebar.title("🔐 بوابة الإدارة")
input_key = st.sidebar.text_input("أدخل مفتاح الأمان (API Key) للوصول لصلاحيات الإدارة:", type="password")

is_admin = False
headers = {}

if input_key:
    if input_key == SYSTEM_API_KEY:
        is_admin = True
        headers = {"X-API-Key": SYSTEM_API_KEY}
        st.sidebar.success("🔑 تم تسجيل الدخول كمدير للنظام بنجاح!")
    else:
        st.sidebar.error("❌ مفتاح الأمان غير صحيح!")
else:
    st.sidebar.info("💡 أدخل مفتاح الأمان في الأعلى لتفعيل لوحة التحكم والإدارة.")

st.sidebar.markdown("---")

# تحديد القوائم المتاحة بناءً على حالة تسجيل الدخول
available_menus = ["🤖 اسأل النظام الذكي (RAG)", "🔍 البحث وعرض تفاصيل المدارس"]

if is_admin:
    available_menus.extend([
        "➕ إضافة مدرسة يدوياً",
        "✏️ تعديل بيانات مدرسة",
        "📄 رفع وتحليل المستندات (Ingest)", 
        "🔍اضافة مدرسة باستخدام نص - بوست فيسبوك, اعلان, ...الخ"
    ])

menu = st.sidebar.selectbox("اختر القسم المتاح لك:", available_menus)

# --- دالة مساعدة لحذف مدرسة من الباك إند ---
def delete_school_request(school_id):
    try:
        response = requests.delete(f"{API_BASE_URL}/schools/{school_id}", headers=headers)
        if response.status_code in [200, 204]:
            return True, "تم حذف المدرسة بنجاح من قاعدة البيانات!"
        else:
            detail = response.json().get("detail", response.text)
            return False, f"فشل الحذف: {detail}"
    except Exception as e:
        return False, f"فشل الاتصال بالخادم: {e}"

# --- 1. قسم السؤال والجواب (RAG) - [عام ومفتوح] ---
if menu == "🤖 اسأل النظام الذكي (RAG)":
    st.header("🤖 اسأل مستندات المدارس")
    st.write("اكتب سؤالك وسيقوم النظام بالبحث في المستندات المرفوعة والإجابة بدقة.")
    
    query = st.text_input("أدخل سؤالك هنا (مثال: ما هي شروط التقديم في مدرسة WE؟):")
    k_val = st.slider("عدد الفقرات المسترجعة للبحث (K):", min_value=1, max_value=10, value=5)
    
    if st.button("اسأل الآن"):
        if query:
            with st.spinner("جاري البحث وتوليد الإجابة..."):
                try:
                    payload = {"question": query, "k": k_val}
                    response = requests.post(f"{API_BASE_URL}/rag/query", json=payload)
                    
                    if response.status_code == 200:
                        result = response.json()
                        st.subheader("💡 الإجابة:")
                        st.success(result["answer"])
                        
                        if result.get("sources"):
                            st.subheader("📌 المصادر المعتمدة:")
                            for i, source in enumerate(result["sources"]):
                                with st.expander(f"مصدر {i+1}: {source['source']} (فقرة رقم {source['chunk_index']}) - نسبة التطابق: {1 - source['distance']:.2f}"):
                                    st.write(f"**مقتطف:** {source['preview']}...")
                    else:
                        st.error(f"خطأ من السيرفر: {response.text}")
                except Exception as e:
                    st.error(f"فشل الاتصال بالخادم: {e}")
        else:
            st.warning("الرجاء إدخال سؤال أولاً.")

# --- 2. قسم البحث وعرض تفاصيل مدرسة معينة [عام ومفتوح] ---
elif menu == "🔍 البحث وعرض تفاصيل المدارس":
    st.header("🔍 استعلام وبحث عن مدرسة محددة")
    st.write("اختر المدرسة التي ترغب في استعراض بياناتها بالكامل من القائمة بالأسفل:")
    
    try:
        response = requests.get(f"{API_BASE_URL}/schools")
        if response.status_code == 200:
            schools = response.json()
            if not schools:
                st.info("لا توجد مدارس مسجلة حالياً في النظام.")
            else:
                school_options = {s["arabic_name"]: s["id"] for s in schools}
                selected_school_name = st.selectbox("ابحث عن المدرسة باختيار اسمها:", ["-- اختر مدرسة من القائمة --"] + list(school_options.keys()))
                
                if selected_school_name != "-- اختر مدرسة من القائمة --":
                    school_id = school_options[selected_school_name]
                    
                    with st.spinner("جاري جلب تفاصيل المدرسة..."):
                        detail_res = requests.get(f"{API_BASE_URL}/schools/{school_id}")
                        
                        if detail_res.status_code == 200:
                            school = detail_res.json()
                            st.markdown("---")
                            st.subheader(f"🏫 {school['arabic_name']}")
                            if school['english_name']:
                                st.caption(f"_{school['english_name']}_")
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                st.info(f"📍 **الموقع:** {school['location']}")
                                st.info(f"🎯 **التخصص:** {school['specialization']}")
                                st.info(f"🤝 **الشريك الصناعي:** {school['industrial_partner'] or 'غير محدد'}")
                                st.info(f"📅 **سنة التأسيس:** {school['established_year']}")
                            with col2:
                                st.success(f"📝 **الحد الأدنى للقبول (المجموع):** {school['minimum_score']} درجة")
                                st.success(f"🌍 **المحافظات المقبولة:** {school['accepted_governorates']}")
                                st.success(f"⏱️ **مدة الدراسة:** {school['study_duration']} سنوات")
                                if school['official_website']:
                                    st.success(f"🌐 **الموقع الإلكتروني:** [{school['official_website']}]({school['official_website']})")
                                else:
                                    st.success("🌐 **الموقع الإلكتروني:** غير متوفر حالياً")
                            
                            st.markdown("#### 📑 نبذة وتفاصيل إضافية:")
                            st.write(school['description'] or "لا توجد تفاصيل إضافية مسجلة لهذه المدرسة.")
                        else:
                            st.error("فشل جلب بيانات المدرسة من الخادم.")
        else:
            st.error("فشل الاتصال بالسيرفر لجلب قائمة المدارس.")
    except Exception as e:
        st.error(f"فشل الاتصال: {e}")

# --- 3. قسم إضافة مدرسة يدوياً [مؤمن ومحمي] ---
elif menu == "➕ إضافة مدرسة يدوياً" and is_admin:
    st.header("➕ إضافة مدرسة تكنولوجيا تطبيقية جديدة")
    st.write("قم بملء النموذج التالي لإضافة مدرسة مباشرة إلى قاعدة البيانات.")
    
    with st.form("add_school_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            arabic_name = st.text_input("اسم المدرسة بالعربي *", placeholder="مثال: مدرسة وي للتكنولوجيا التطبيقية")
            english_name = st.text_input("اسم المدرسة بالإنجليزي (اختياري)", placeholder="مثال: WE Applied Technology School")
            established_year = st.number_input("سنة التأسيس *", min_value=2015, max_value=2030, value=2024)
            specialization = st.text_input("التخصص الرئيسي *", placeholder="مثال: اتصالات وتكنولوجيا معلومات")
            location = st.text_input("الموقع / العنوان *", placeholder="مثال: مدينة نصر، القاهرة")
        
        with col2:
            accepted_governorates = st.text_input("المحافظات المقبولة *", value="All", placeholder="مثال: القاهرة، الجيزة، القليوبية")
            minimum_score = st.number_input("الحد الأدنى للقبول (المجموع) *", min_value=140, max_value=280, value=240)
            industrial_partner = st.text_input("الشريك الصناعي (اختياري)", placeholder="مثال: الشركة المصرية للاتصالات")
            study_duration = st.number_input("مدة الدراسة بالسنوات *", min_value=3, max_value=5, value=3)
            official_website = st.text_input("الموقع الإلكتروني الرسمي (اختياري)", placeholder="https://example.com")
            
        description = st.text_area("وصف وتفاصيل إضافية عن المدرسة (اختياري)", placeholder="اكتب نبذة مختصرة هنا...")
        
        st.markdown("<small>* تعني أن الحقل مطلوب إجباريًا</small>", unsafe_allow_html=True)
        submit_btn = st.form_submit_button("حفظ وإضافة المدرسة")
        
        if submit_btn:
            if not arabic_name or not specialization or not location or not accepted_governorates:
                st.error("⚠️ يرجى ملء جميع الحقول المطلوبة المميزة بـ (*).")
            else:
                payload = {
                    "arabic_name": arabic_name,
                    "english_name": english_name if english_name else None,
                    "established_year": int(established_year),
                    "specialization": specialization,
                    "location": location,
                    "accepted_governorates": accepted_governorates,
                    "minimum_score": int(minimum_score),
                    "industrial_partner": industrial_partner if industrial_partner else None,
                    "study_duration": int(study_duration),
                    "description": description if description else None,
                    "official_website": official_website if official_website else None
                }
                
                with st.spinner("جاري حفظ البيانات..."):
                    try:
                        response = requests.post(f"{API_BASE_URL}/schools", json=payload, headers=headers)
                        if response.status_code in [200, 201]:
                            st.success(f"🎉 تم إضافة مدرسة '{arabic_name}' بنجاح لقاعدة البيانات!")
                            st.balloons()
                        else:
                            st.error(f"❌ فشل الإضافة: {response.text}")
                    except Exception as e:
                        st.error(f"❌ فشل الاتصال بالخادم: {e}")

# --- 4. قسم تعديل وحذف بيانات مدرسة [مؤمن ومحمي] ---
elif menu == "✏️ تعديل بيانات مدرسة" and is_admin:
    st.header("✏️ تعديل وإدارة بيانات المدارس المسجلة")
    st.write("اختر المدرسة التي ترغب في تعديل بياناتها أو حذفها.")

    try:
        schools_res = requests.get(f"{API_BASE_URL}/schools")
        if schools_res.status_code == 200:
            schools_list = schools_res.json()
            if not schools_list:
                st.info("لا توجد مدارس مسجلة حالياً لإدارتها.")
            else:
                school_options = {s["arabic_name"]: s["id"] for s in schools_list}
                selected_school_name = st.selectbox("اختر المدرسة المستهدفة:", ["-- اختر مدرسة --"] + list(school_options.keys()))
                
                if selected_school_name != "-- اختر مدرسة --":
                    school_id = school_options[selected_school_name]
                    
                    # جلب تفاصيل المدرسة المحددة لتعبئة الفورم
                    with st.spinner("جاري جلب تفاصيل المدرسة الحالية..."):
                        detail_res = requests.get(f"{API_BASE_URL}/schools/{school_id}")
                        
                        if detail_res.status_code == 200:
                            selected_school = detail_res.json()
                            
                            st.markdown("---")
                            
                            # زر الحذف السريع والمباشر (مع تأكيد الأمان) خارج الفورم الرئيسي
                            st.subheader("🗑️ منطقة الحذف السريع (إجراء خطير):")
                            col_del, col_info = st.columns([1, 3])
                            with col_del:
                                # حيلة برمجية لجعل الزر يظهر باللون الأحمر عن طريق CSS المخصص المضاف بالأعلى
                                st.markdown('<div class="delete-btn">', unsafe_allow_html=True)
                                confirm_delete = st.button("احذف هذه المدرسة نهائياً! 🗑️")
                                st.markdown('</div>', unsafe_allow_html=True)
                            with col_info:
                                st.warning("تنبيه: عملية الحذف نهائية ولا يمكن التراجع عنها بعد تأكيد الإجراء.")
                            
                            if confirm_delete:
                                with st.spinner("جاري حذف المدرسة..."):
                                    success, msg = delete_school_request(school_id)
                                    if success:
                                        st.success(msg)
                                        st.balloons()
                                        st.rerun()
                                    else:
                                        st.error(msg)
                            
                            st.markdown("---")
                            st.subheader(f"🔄 تحديث بيانات: {selected_school['arabic_name']}")
                            
                            # نموذج التحديث
                            with st.form("edit_school_form"):
                                col1, col2 = st.columns(2)
                                
                                with col1:
                                    new_arabic_name = st.text_input("اسم المدرسة بالعربي *", value=selected_school["arabic_name"])
                                    new_english_name = st.text_input("اسم المدرسة بالإنجليزي", value=selected_school["english_name"] or "")
                                    new_established_year = st.number_input("سنة التأسيس *", min_value=2015, max_value=2030, value=int(selected_school["established_year"]))
                                    new_specialization = st.text_input("التخصص الرئيسي *", value=selected_school["specialization"])
                                    new_location = st.text_input("الموقع / العنوان *", value=selected_school["location"])
                                
                                with col2:
                                    new_accepted_governorates = st.text_input("المحافظات المقبولة *", value=selected_school["accepted_governorates"])
                                    new_minimum_score = st.number_input("الحد الأدنى للقبول *", min_value=140, max_value=280, value=int(selected_school["minimum_score"]))
                                    new_industrial_partner = st.text_input("الشريك الصناعي", value=selected_school["industrial_partner"] or "")
                                    new_study_duration = st.number_input("مدة الدراسة بالسنوات *", min_value=3, max_value=5, value=int(selected_school["study_duration"]))
                                    new_official_website = st.text_input("الموقع الإلكتروني الرسمي", value=selected_school["official_website"] or "")
                                    
                                new_description = st.text_area("وصف وتفاصيل إضافية", value=selected_school["description"] or "")
                                
                                update_btn = st.form_submit_button("حفظ وتطبيق التعديلات")
                                
                                if update_btn:
                                    payload = {
                                        "arabic_name": new_arabic_name,
                                        "english_name": new_english_name if new_english_name else None,
                                        "established_year": int(new_established_year),
                                        "specialization": new_specialization,
                                        "location": new_location,
                                        "accepted_governorates": new_accepted_governorates,
                                        "minimum_score": int(new_minimum_score),
                                        "industrial_partner": new_industrial_partner if new_industrial_partner else None,
                                        "study_duration": int(new_study_duration),
                                        "description": new_description if new_description else None,
                                        "official_website": new_official_website if new_official_website else None
                                    }
                                    
                                    with st.spinner("جاري حفظ التعديلات بالسيرفر..."):
                                        try:
                                            response = requests.patch(f"{API_BASE_URL}/schools/{school_id}", json=payload, headers=headers)
                                            if response.status_code == 200:
                                                st.success(f"🎉 تم تحديث بيانات مدرسة '{new_arabic_name}' بنجاح!")
                                                st.balloons()
                                                st.rerun()
                                            else:
                                                st.error(f"❌ فشل التحديث: {response.text}")
                                        except Exception as e:
                                            st.error(f"❌ فشل الاتصال بالخادم: {e}")
                        else:
                            st.error("فشل استرجاع بيانات المدرسة المختارة للتعديل.")
        else:
            st.error("فشل في جلب قائمة المدارس من السيرفر.")
    except Exception as e:
        st.error(f"حدث خطأ أثناء الاتصال: {e}")

# --- 5. قسم رفع المستندات (Ingest) - [مؤمن ومحمي] ---
elif menu == "📄 رفع وتحليل المستندات (Ingest)" and is_admin:
    st.header("📄 رفع ملفات PDF إلى قاعدة المعرفة (صلاحيات الإدارة)")
    st.write("قم برفع ملفات الـ PDF ليتم معالجتها وحفظها للبحث لاحقاً.")
    
    uploaded_file = st.file_uploader("اختر ملف PDF للرفع:", type=["pdf"])
    
    if st.button("تحميل ومعالجة الملف"):
        if uploaded_file is not None:
            with st.spinner("جاري رفع ومعالجة الملف..."):
                try:
                    files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
                    response = requests.post(f"{API_BASE_URL}/rag/ingest", files=files, headers=headers)
                    
                    if response.status_code == 200:
                        res_data = response.json()
                        st.success(f"✔️ {res_data['message']}")
                        st.info(f"اسم الملف: {res_data['filename']} | عدد الفقرات المضافة: {res_data['chunks_ingested']}")
                    else:
                        st.error(f"حدث خطأ أثناء الرفع: {response.text}")
                except Exception as e:
                    st.error(f"فشل الاتصال بالخادم: {e}")
        else:
            st.warning("الرجاء اختيار ملف أولاً.")
            
    st.markdown("---")
    st.subheader("📋 المستندات المرفوعة حالياً:")
    if st.button("تحديث قائمة المستندات"):
        try:
            res = requests.get(f"{API_BASE_URL}/rag/sources", headers=headers)
            if res.status_code == 200:
                sources = res.json()
                if not sources:
                    st.info("لا توجد مستندات مرفوعة حالياً.")
                else:
                    for src in sources:
                        st.write(f"- 📄 **{src['source']}** (عدد الفقرات: {src['chunk_count']}) - تم الرفع: {src['last_ingested']}")
            else:
                st.error("فشل في جلب قائمة المستندات.")
        except Exception as e:
            st.error(f"فشل الاتصال: {e}")

# --- 6. قسم استخراج البيانات بالذكاء الاصطناعي - [مؤمن ومحمي] ---
elif menu == "🔍 اضافة مدرسة باستخدام نص - بوست فيسبوك, اعلان, ...الخ" and is_admin:
    st.header("🔍 استخراج تفاصيل المدرسة تلقائياً (صلاحيات الإدارة)")
    st.write("ضع نصاً يتحدث عن مدرسة تكنولوجيا تطبيقية وسيقوم الذكاء الاصطناعي باستخراج حقولها وحفظها مباشرة.")
    
    school_text = st.text_area("أدخل النص التعريفي بالمدرسة:", height=150, placeholder="اكتب هنا النص العربي الشامل عن المدرسة...")
    provider = st.selectbox("مزود خدمة الذكاء الاصطناعي (Provider):", ["groq", "hf"])
    
    if st.button("استخراج وحفظ البيانات"):
        if len(school_text) >= 10:
            with st.spinner("جاري التحليل واستخراج البيانات وحفظها..."):
                try:
                    payload = {"text": school_text, "provider": provider}
                    response = requests.post(f"{API_BASE_URL}/llm/extract-school", json=payload, headers=headers)
                    
                    if response.status_code == 200:
                        school_data = response.json()
                        st.success("🎉 تم استخراج البيانات وحفظ المدرسة بنجاح في قاعدة البيانات!")
                        st.json(school_data)
                    else:
                        st.error(f"فشل الاستخراج. (تأكد من صحة الـ API Key أو اكتمال البيانات بالنص، خطأ: {response.text})")
                except Exception as e:
                    st.error(f"حدث خطأ أثناء المعالجة: {e}")
        else:
            st.warning("يجب أن يحتوي النص على 10 أحرف على الأقل.")
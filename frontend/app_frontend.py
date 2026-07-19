import os
import streamlit as st
import requests
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="منصة مدارس التكنولوجيا التطبيقية الذكية",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# الإعدادات والربط مع السيرفر
# ==========================================
try:
    API_BASE_URL = st.secrets["API_BASE_URL"]
    SYSTEM_API_KEY = st.secrets["API_KEY"]
except Exception:
    API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
    SYSTEM_API_KEY = os.getenv("API_KEY")

# تحسين المظهر ودعم اللغة العربية (RTL) بشكل متناسق ومريح للعين
st.markdown("""
    <style>
    .main .block-container {
        direction: rtl;
        text-align: right;
    }
    .main h1, .main h2, .main h3, .main h4, .main p, .main span, .main div {
        direction: rtl;
        text-align: right;
    }
    .school-card {
        background-color: #f8f9fa;
        border-right: 5px solid #007bff;
        padding: 20px;
        border-radius: 8px;
        margin-bottom: 15px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .metric-box {
        background-color: #e9ecef;
        padding: 10px 15px;
        border-radius: 6px;
        text-align: center;
        font-weight: bold;
    }
    </style>
    """, unsafe_allow_html=True)

headers = {"X-API-Key": SYSTEM_API_KEY} if SYSTEM_API_KEY else {}

# ==========================================
# القائمة الجانبية للتصفح
# ==========================================
st.sidebar.title("🎓 القائمة الرئيسية")

if "is_admin" not in st.session_state:
    st.session_state.is_admin = False

with st.sidebar.expander("🔐 لوحة تحكم الإدارة (خاص بالمسؤولين)"):
    if not st.session_state.is_admin:
        admin_key = st.text_input("أدخل كلمة مرور المسؤول:", type="password")
        if st.button("تسجيل الدخول"):
            if admin_key == SYSTEM_API_KEY:
                st.session_state.is_admin = True
                st.success("تم تفعيل صلاحيات الإدارة!")
                st.rerun()
            else:
                st.error("الكلمة غير صحيحة!")
    else:
        st.write("🟢 أنت تعمل الآن بصلاحيات المشرف.")
        if st.button("تسجيل الخروج"):
            st.session_state.is_admin = False
            st.rerun()

is_admin = st.session_state.is_admin

# تبسيط أسماء الأقسام للمستخدم العادي
menu_options = ["🏠 دليل واستعراض المدارس", "💬 المستشار الذكي (اسأل عن أي مدرسة)"]
if is_admin:
    menu_options.extend([
        "➕ إضافة مدرسة جديدة", 
        "📝 استخراج بيانات مدرسة من نص",
        "📂 رفع ملفات وأدلة المدارس"
    ])

menu = st.sidebar.radio("اختر الوجهة:", menu_options)

# ==========================================
# 1. شاشة دليل واستعراض المدارس (UI مُحسّن)
# ==========================================
if menu == "🏠 دليل واستعراض المدارس":
    st.title("🏫 دليل مدارس التكنولوجيا التطبيقية بمصر")
    st.write("اكتشف وتصفح شروط وتفاصيل المدارس المسجلة في النظام للعام الدراسي الحالي.")

    with st.spinner("جاري تحديث قائمة المدارس..."):
        try:
            res = requests.get(f"{API_BASE_URL}/schools")
            if res.status_code == 200:
                schools = res.json()
                if not schools:
                    st.info("لا توجد مدارس مسجلة في الدليل حتى الآن.")
                else:
                    # عرض إجمالي المدارس بشكل جمالي
                    st.markdown(f"### 📊 إجمالي المدارس المتوفرة: `{len(schools)}` مدارس")
                    st.write("---")
                    
                    for school in schools:
                        # تنسيق وعرض بطاقة المدرسة بشكل احترافي ومبسط
                        st.markdown(f"""
                        <div class="school-card">
                            <h2 style='margin-top:0; color:#0056b3;'>🏫 {school['arabic_name']}</h2>
                            <p style='font-size:16px; color:#555;'>{school['description'] or 'لا يوجد وصف تفصيلي متوفر حالياً لهذه المدرسة.'}</p>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # تفاصيل إضافية مقسمة في أعمدة
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.markdown(f"🎯 **التخصص الدراسي:**\n{school['specialization']}")
                            st.markdown(f"🤝 **الشريك الصناعي:**\n{school['industrial_partner'] or 'غير محدد'}")
                        with col2:
                            st.markdown(f"📍 **الموقع الجغرافي:**\n{school['location']}")
                            st.markdown(f"🌍 **المحافظات المقبولة:**\n{school['accepted_governorates']}")
                        with col3:
                            st.markdown(f"⏱️ **مدة الدراسة:**\n{school['study_duration']} سنوات")
                            st.markdown(f"📅 **سنة التأسيس:**\nعام {school['established_year']}")
                        
                        # إبراز مجموع التنسيق والموقع الإلكتروني
                        col_btn1, col_btn2 = st.columns([1, 2])
                        with col_btn1:
                            st.markdown(f"<div class='metric-box'>📊 الحد الأدنى: {school['minimum_score']} درجة</div>", unsafe_allow_html=True)
                        with col_btn2:
                            if school['official_website']:
                                st.link_button("🌐 زيارة الموقع الرسمي للمدرسة", school['official_website'])
                        
                        if is_admin:
                            if st.button(f"🗑️ حذف هذه المدرسة", key=f"del_{school['id']}"):
                                del_res = requests.delete(f"{API_BASE_URL}/schools/{school['id']}", headers=headers)
                                if del_res.status_code == 204:
                                    st.success("تم حذف المدرسة من النظام بنجاح!")
                                    st.rerun()
                                else:
                                    st.error("فشل حذف المدرسة.")
                        st.markdown("<br><hr style='border-top: 1px dashed #ccc;'><br>", unsafe_allow_html=True)
            else:
                st.error("فشل الاتصال بخادم البيانات.")
        except Exception as e:
            st.error(f"خطأ في الاتصال بالـ Backend: {e}")

# ==========================================
# 2. شاشة المستشار الذكي (RAG Query)
# ==========================================
elif menu == "💬 المستشار الذكي (اسأل عن أي مدرسة)":
    st.title("💬 المستشار الذكي للمدارس")
    st.write("اختر المدرسة التي تود الاستفسار عنها، واكتب سؤالك ليقوم الذكاء الاصطناعي بالإجابة مباشرة من واقع ملفاتها الرسمية المعتمدة.")

    try:
        schools_res = requests.get(f"{API_BASE_URL}/schools")
        if schools_res.status_code == 200 and schools_res.json():
            schools_list = schools_res.json()
            school_options = {s["arabic_name"]: s["id"] for s in schools_list}
            
            selected_school_name = st.selectbox("حدد المدرسة التي تريد الاستفسار عنها:", list(school_options.keys()))
            selected_school_id = school_options[selected_school_name]

            user_question = st.text_input("اكتب سؤالك هنا (مثال: ما هي شروط التقديم والأوراق المطلوبة؟):")
            
            if st.button("إرسال السؤال"):
                if user_question.strip():
                    with st.spinner("جاري مراجعة أدلة الملفات والإجابة على سؤالك بدقة..."):
                        try:
                            payload = {
                                "question": user_question,
                                "school_id": selected_school_id,
                                "k": 6
                            }
                            response = requests.post(f"{API_BASE_URL}/rag/query", json=payload, headers=headers)
                            
                            if response.status_code == 200:
                                data = response.json()
                                st.markdown("### 🤖 إجابة المستشار الذكي:")
                                st.info(data["answer"])
                                
                                with st.expander("🔍 مراجعة المصادر المعتمدة المأخوذ منها الإجابة:"):
                                    for src in data["sources"]:
                                        st.write(f"- تم الاستناد إلى ملف: `{src['source']}`")
                            else:
                                st.warning("تنبيه: لم يتم رفع ملفات دليل الطالب لهذه المدرسة بعد، أو حدثت مشكلة في السيرفر.")
                        except Exception as e:
                            st.error(f"فشل الاتصال: {e}")
                else:
                    st.warning("يرجى كتابة سؤال أولاً.")
        else:
            st.warning("⚠️ لا توجد مدارس مسجلة بالنظام حالياً للاستعلام عنها.")
    except Exception as e:
        st.error(f"خطأ في تحميل قائمة المدارس: {e}")

# ==========================================
# 3. شاشة إضافة مدرسة يدوياً (Admin)
# ==========================================
elif menu == "➕ إضافة مدرسة جديدة" and is_admin:
    st.header("➕ تسجيل مدرسة جديدة في الدليل")
    
    with st.form("add_school_form"):
        arabic_name = st.text_input("اسم المدرسة باللغة العربية (مطلوب):")
        english_name = st.text_input("اسم المدرسة باللغة الإنجليزية (اختياري):")
        established_year = st.number_input("سنة التأسيس:", min_value=2015, max_value=2030, value=2023)
        specialization = st.text_input("التخصصات الدراسية المتاحة:")
        location = st.text_input("المحافظة والمنطقة السكنية:")
        accepted_governorates = st.text_input("المحافظات التي يُسمح لطلابها بالتقديم:", value="جميع المحافظات")
        minimum_score = st.number_input("الحد الأدنى للمجموع في الشهادة الإعدادية:", min_value=140, max_value=280, value=220)
        industrial_partner = st.text_input("الشريك الصناعي أو الهيئة المشرفة:")
        study_duration = st.number_input("عدد سنوات الدراسة بالنظام:", min_value=3, max_value=5, value=3)
        description = st.text_area("نبذة تعريفية ومميزات المدرسة للطلاب:")
        official_website = st.text_input("رابط الموقع أو الصفحة الرسمية للتسجيل:")
        
        submitted = st.form_submit_button("حفظ المدرسة وتفعيلها فوراً")
        if submitted:
            if not arabic_name or not specialization or not location:
                st.error("يرجى تعبئة الحقول الأساسية (الاسم، التخصص، والموقع).")
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
                with st.spinner("جاري حفظ البيانات المحدثة..."):
                    try:
                        res = requests.post(f"{API_BASE_URL}/schools", json=payload, headers=headers)
                        if res.status_code == 201:
                            st.success(f"🎉 تم إضافة وتفعيل مدرسة '{arabic_name}' بنجاح في الدليل العلني!")
                        else:
                            st.error(f"فشل الحفظ: {res.text}")
                    except Exception as e:
                        st.error(f"حدث خطأ غير متوقع: {e}")

# ==========================================
# 4. شاشة استخراج وحفظ مدرسة بنص (Admin)
# ==========================================
elif menu == "📝 استخراج بيانات مدرسة من نص" and is_admin:
    st.header("📝 استخراج وتعبئة بيانات المدارس تلقائياً")
    st.write("أضف أي نص عشوائي (مثل منشور فيسبوك، إعلان رسمي، أو بيان صحفي) وسيتولى الذكاء الاصطناعي تفكيكه وتعبئة بيانات المدرسة تلقائياً وحفظها.")
    
    school_text = st.text_area("الصق النص هنا:", height=150, placeholder="اكتب أو الصق المنشور التعريفي بالمدرسة...")
    provider = st.selectbox("محرك التحليل الذكي المفضل:", ["groq", "hf"])
    
    if st.button("تحليل النص وحفظ المدرسة"):
        if len(school_text) >= 10:
            with st.spinner("جاري قراءة النص واستخراج البيانات الهيكلية بدقة..."):
                try:
                    payload = {"text": school_text, "provider": provider}
                    response = requests.post(f"{API_BASE_URL}/llm/extract-school", json=payload, headers=headers)
                    
                    if response.status_code == 200:
                        st.success("🎉 نجح الذكاء الاصطناعي في تحليل البيانات وحفظ المدرسة بالكامل في الدليل!")
                        st.json(response.json())
                    else:
                        st.error("فشل التحليل، يرجى التأكد من احتواء النص على بيانات كافية.")
                except Exception as e:
                    st.error(f"خطأ أثناء معالجة الطلب: {e}")
        else:
            st.warning("يرجى إدخال نص تعريفي أطول للتمكن من تحليله.")

# ==========================================
# 5. شاشة رفع الدليل الجديد (RAG Ingest)
# ==========================================
elif menu == "📂 رفع ملفات وأدلة المدارس" and is_admin:
    st.header("📂 إدارة ورفع ملفات المعرفة للمدارس")
    st.write("ارفع كتب الشروط والأدلة الرسمية (بصيغة PDF) ليستخدمها المستشار الذكي كمرجع موثوق.")
    
    try:
        schools_res = requests.get(f"{API_BASE_URL}/schools")
        if schools_res.status_code == 200 and schools_res.json():
            schools_list = schools_res.json()
            school_options = {s["arabic_name"]: s["id"] for s in schools_list}
            
            selected_school_name = st.selectbox("اختر المدرسة المستهدفة برفع هذا الملف:", list(school_options.keys()))
            selected_school_id = school_options[selected_school_name]

            uploaded_file = st.file_uploader("اختر ملف الدليل الرسمي للطالب (PDF فقط):", type=["pdf"])
            
            if st.button("بدأ معالجة وحفظ الملف"):
                if uploaded_file is not None:
                    with st.spinner("جاري قراءة الملف وتخزينه في مساحة المعرفة المعزولة للمدرسة..."):
                        try:
                            files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
                            res = requests.post(f"{API_BASE_URL}/rag/ingest?school_id={selected_school_id}", files=files, headers=headers)
                            
                            if res.status_code == 200:
                                st.success(f"🎉 تم تكشيف ودمج ملف مدرسة ({selected_school_name}) بنجاح في قاعدة البيانات المعزولة!")
                                st.json(res.json())
                            else:
                                st.error(f"فشل دمج الملف: {res.text}")
                        except Exception as e:
                            st.error(f"خطأ أثناء معالجة السيرفر: {e}")
                else:
                    st.warning("يرجى اختيار ملف PDF أولاً لرفعه.")
        else:
            st.warning("⚠️ لا توجد مدارس مسجلة، يرجى تسجيل مدرسة أولاً لربط الملفات بها.")
    except Exception as e:
        st.error(f"فشل جلب قائمة المدارس: {e}")
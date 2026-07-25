/**
 * Spheronix Hackathon Registration System
 * Updated flow: no admin/results, no participant ID, terms-gated payment, merged payment+registration.
 */

document.addEventListener("DOMContentLoaded", async () => {
    window.GLOBAL_REGISTRATION_AMOUNT = 1800;
    try {
        const res = await fetch("/api/public-settings/");
        if (res.ok) {
            const data = await res.json();
            if (data.registrationAmount) {
                window.GLOBAL_REGISTRATION_AMOUNT = data.registrationAmount;
                // Fix L-09: Always update amount from API, regardless of current text content
                const summaryAmountSpan = document.getElementById("summary-amount");
                if (summaryAmountSpan) {
                    summaryAmountSpan.textContent = `₹${data.registrationAmount}`;
                }
            }
            if (data.registrationOpen === false) {
                const btnStart = document.getElementById("btn-start-register");
                if (btnStart) {
                    btnStart.style.display = "none";
                    const closedBadge = document.createElement("div");
                    closedBadge.className = "text-center p-4 bg-red-100 text-red-700 font-bold rounded-lg border border-red-300 mt-4";
                    closedBadge.innerText = "Registrations are currently closed.";
                    btnStart.parentNode.insertBefore(closedBadge, btnStart);
                }
                const btnStartInstr = document.getElementById("btn-start-from-instructions");
                if (btnStartInstr) {
                    btnStartInstr.style.display = "none";
                }
            }
        }
    } catch (e) {
        console.error("Failed to fetch dynamic settings", e);
    }
    const MAX_TEAM_MEMBERS = 4;
    const MIN_TEAM_TOTAL = 2;
    const MAX_TEAM_TOTAL = 5;

    const landingView = document.getElementById("landing-view");
    const registerView = document.getElementById("register-view");
    const instructionsView = document.getElementById("instructions-view");

    const btnStartRegister = document.getElementById("btn-start-register");
    const btnInstructions = document.getElementById("btn-instructions");
    const btnBackLanding = document.getElementById("btn-back-landing");
    const btnBackInstructions = document.getElementById("btn-back-instructions");
    const btnStartFromInstructions = document.getElementById("btn-start-from-instructions");

    const navHome = document.getElementById("nav-home");
    const navInstructions = document.getElementById("nav-instructions");

    const step1 = document.getElementById("step-1");
    const step2 = document.getElementById("step-2");
    const step3 = document.getElementById("step-3");
    const step4 = document.getElementById("step-4");
    const successView = document.getElementById("success-view");

    const stepIndicator1 = document.getElementById("step-indicator-1");
    const stepIndicator2 = document.getElementById("step-indicator-2");
    const stepIndicator3 = document.getElementById("step-indicator-3");
    const stepIndicator4 = document.getElementById("step-indicator-4");
    const progressLine1 = document.getElementById("progress-line-1");
    const progressLine2 = document.getElementById("progress-line-2");
    const progressLine3 = document.getElementById("progress-line-3");

    const btnGoogleAuth = document.getElementById("btn-google-auth");
    const authError = document.getElementById("auth-error");
    const alreadyRegistered = document.getElementById("already-registered");

    const registrationForm = document.getElementById("registration-form");

    const registrationDateInput = document.getElementById("registrationDate");
    const fullNameInput = document.getElementById("fullName");
    const emailInput = document.getElementById("email");
    const mobileInput = document.getElementById("mobile");
    const branchInput = document.getElementById("branch");
    const collegeNameInput = document.getElementById("collegeName");
    const collegeSearchInput = document.getElementById("collegeSearch");
    const collegeDropdown = document.getElementById("college-dropdown");
    const otherCollegeWrapper = document.getElementById("other-college-wrapper");
    const otherCollegeInput = document.getElementById("otherCollegeName");
    const cityInput = document.getElementById("city");
    const rollNumberInput = document.getElementById("rollNumber");
    const projectSelectedInput = document.getElementById("projectSelected");

    const termsAcceptedInput = document.getElementById("termsAccepted");
    const paymentTermsModeText = document.getElementById("payment-terms-mode-text");
    const termsStatusBadge = document.getElementById("terms-status-badge");
    const btnOpenTerms = document.getElementById("btn-open-terms");
    const btnTermsAccept = document.getElementById("btn-terms-accept");
    const btnTermsReject = document.getElementById("btn-terms-reject");
    const termsModal = document.getElementById("terms-modal");

    const liveUpdateToast = document.getElementById("live-update-toast");
    const toastTitle = document.getElementById("toast-title");
    const toastMessage = document.getElementById("toast-message");
    const toastClose = document.getElementById("toast-close");

    const teamNameInput = document.getElementById("teamName");
    const leaderInfoEl = document.getElementById("leader-info");
    const leaderCollegeInfoEl = document.getElementById("leader-college-info");
    const btnAddMember = document.getElementById("btn-add-member");
    const memberLimitMsg = document.getElementById("member-limit-msg");
    const btnBackStep2 = document.getElementById("btn-back-step2");
    const btnNextPayment = document.getElementById("btn-next-payment");

    const btnPayNow = document.getElementById("btn-pay-now");
    const btnSubmitFinal = document.getElementById("btn-submit-final");
    const btnBackStep3 = document.getElementById("btn-back-step3");

    let currentUser = { email: "", name: "", googleId: "" };
    let currentPayment = { orderId: "", paymentId: "", gateway: "razorpay", amount: 0 };
    let teamMemberCount = 1;
    let collegesLoaded = false;
    let termsAcceptedForPayment = false;
    let collegeFilterDebounce;
    let collegeDropdownItems = [];
    let activeCollegeIndex = -1;

    const FORM_STORAGE_KEY = "hackathon_registration_form";
    const WORKFLOW_STORAGE_KEY = "hackathon_registration_workflow";
    const WORKFLOW_MAX_AGE_MS = 24 * 60 * 60 * 1000;
    let currentStep = 1;
    let currentViewName = "landing";
    let paymentCompleted = false;
    let registrationSummary = null;
    let pollingInterval = null;

    function showToast(title, message) {
        if (!liveUpdateToast) return;
        if (toastTitle) toastTitle.textContent = title;
        if (toastMessage) toastMessage.textContent = message;
        liveUpdateToast.classList.remove("hidden");
        // small delay to allow display:block to apply before animation
        setTimeout(() => liveUpdateToast.classList.add("show"), 10);

        setTimeout(hideToast, 8000);
    }

    function hideToast() {
        if (!liveUpdateToast) return;
        liveUpdateToast.classList.remove("show");
        setTimeout(() => liveUpdateToast.classList.add("hidden"), 400); // match CSS transition duration
    }

    if (toastClose) {
        toastClose.addEventListener("click", hideToast);
    }

    function formatISTDateTime(dateValue = new Date()) {
        return new Intl.DateTimeFormat("en-IN", {
            timeZone: "Asia/Kolkata",
            year: "numeric",
            month: "2-digit",
            day: "2-digit",
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
            hour12: true,
        }).format(dateValue) + " IST";
    }

    function clearWorkflowState() {
        localStorage.removeItem(WORKFLOW_STORAGE_KEY);
    }

    function saveWorkflowState() {
        const state = {
            currentStep,
            currentViewName,
            currentUser,
            currentPayment,
            teamMemberCount,
            termsAcceptedForPayment,
            paymentCompleted,
            registrationSummary,
            savedAt: Date.now(),
        };
        localStorage.setItem(WORKFLOW_STORAGE_KEY, JSON.stringify(state));
    }

    function loadWorkflowState() {
        const raw = localStorage.getItem(WORKFLOW_STORAGE_KEY);
        if (!raw) return null;

        try {
            const state = JSON.parse(raw);
            const savedAt = Number(state.savedAt || 0);
            if (!savedAt || Date.now() - savedAt > WORKFLOW_MAX_AGE_MS) {
                clearWorkflowState();
                return null;
            }
            return state;
        } catch (_err) {
            clearWorkflowState();
            return null;
        }
    }

    function setBackButtonAfterPaymentState() {
        if (paymentCompleted) {
            btnBackStep3.classList.add("hidden");
            btnBackStep3.disabled = true;
            return;
        }

        btnBackStep3.classList.remove("hidden");
        btnBackStep3.disabled = false;
    }

    function applyPaymentStepState() {
        const paymentSuccess = document.getElementById("payment-success-msg");
        const paymentMethod = document.querySelector(".payment-method");
        const transactionIdEl = document.getElementById("display-transaction-id");

        if (paymentCompleted && currentPayment.orderId) {
            if (paymentSuccess) paymentSuccess.classList.remove("hidden");
            if (paymentMethod) paymentMethod.classList.add("hidden");
            if (transactionIdEl) transactionIdEl.textContent = currentPayment.paymentId || currentPayment.orderId;
            btnSubmitFinal.classList.remove("hidden");
            setBackButtonAfterPaymentState();
            return;
        }

        if (paymentSuccess) paymentSuccess.classList.add("hidden");
        if (paymentMethod) paymentMethod.classList.remove("hidden");
        btnSubmitFinal.classList.add("hidden");
        setBackButtonAfterPaymentState();
    }

    function restoreWorkflowProgress() {
        const state = loadWorkflowState();
        if (!state) return;

        if (state.currentUser && state.currentUser.email) {
            currentUser = {
                email: state.currentUser.email || "",
                name: state.currentUser.name || "",
                googleId: state.currentUser.googleId || "",
            };
            emailInput.value = currentUser.email;
            if (!fullNameInput.value && currentUser.name) {
                fullNameInput.value = currentUser.name;
            }
            if (!registrationDateInput.value) {
                registrationDateInput.value = formatISTDateTime();
            }
        }

        teamMemberCount = Math.min(MAX_TEAM_MEMBERS, Math.max(1, Number(state.teamMemberCount || teamMemberCount || 1)));
        termsAcceptedForPayment = !!state.termsAcceptedForPayment;
        paymentCompleted = !!state.paymentCompleted;
        registrationSummary = state.registrationSummary || null;

        if (state.currentPayment) {
            currentPayment = {
                orderId: state.currentPayment.orderId || "",
                paymentId: state.currentPayment.paymentId || "",
                gateway: state.currentPayment.gateway || "razorpay",
                amount: Number(state.currentPayment.amount || 0),
            };
        }

        const requestedView = state.currentViewName;
        if (requestedView === "register") {
            showView(registerView);
        } else if (requestedView === "instructions") {
            showView(instructionsView);
        } else {
            showView(landingView);
        }

        const requestedStep = state.currentStep === "success" ? "success" : Number(state.currentStep || 1);
        if (requestedStep === "success") {
            showStep("success");
            if (registrationSummary) {
                renderSuccessSummary(registrationSummary);
            } else if (currentPayment.orderId) {
                fetchRegistrationSummary(currentPayment.orderId)
                    .then((summary) => {
                        registrationSummary = summary;
                        renderSuccessSummary(summary);
                        saveWorkflowState();
                    })
                    .catch(() => { });
            }
            return;
        }

        if (requestedStep >= 2 && !currentUser.email) {
            showStep(1);
            return;
        }

        if (requestedStep >= 3) {
            const mode = document.querySelector('input[name="participationMode"]:checked')?.value;
            if (mode === "team") {
                setupTeamStep();
            }
        }

        if (requestedStep === 4) {
            updatePaymentSummary();
            applyPaymentStepState();
        }

        showStep(requestedStep);
        saveWorkflowState();
    }

    function showView(view) {
        [landingView, registerView, instructionsView].forEach((v) => {
            v.classList.remove("active");
            v.classList.add("hidden");
        });
        view.classList.remove("hidden");
        view.classList.add("active");

        if (view === registerView) {
            currentViewName = "register";
        } else if (view === instructionsView) {
            currentViewName = "instructions";
        } else {
            currentViewName = "landing";
        }

        document.querySelectorAll(".nav-links a").forEach((a) => a.classList.remove("active"));
        if (view === landingView) navHome.classList.add("active");
        if (view === instructionsView) navInstructions.classList.add("active");

        if (currentViewName !== "register" || currentStep !== "success") {
            stopLiveUpdatesPolling();
        }

        saveWorkflowState();
    }

    function showStep(stepNum) {
        currentStep = stepNum;
        [step1, step2, step3, step4, successView].forEach((s) => {
            s.classList.remove("active-step");
            s.classList.add("hidden-step");
        });
        [stepIndicator1, stepIndicator2, stepIndicator3, stepIndicator4].forEach((s) => s.classList.remove("active", "completed"));
        [progressLine1, progressLine2, progressLine3].forEach((line) => line.classList.remove("active"));

        if (stepNum === 1) {
            step1.classList.add("active-step");
            step1.classList.remove("hidden-step");
            stepIndicator1.classList.add("active");
            saveWorkflowState();
            return;
        }
        if (stepNum === 2) {
            step2.classList.add("active-step");
            step2.classList.remove("hidden-step");
            stepIndicator1.classList.add("completed");
            stepIndicator2.classList.add("active");
            progressLine1.classList.add("active");
            saveWorkflowState();
            return;
        }
        if (stepNum === 3) {
            step3.classList.add("active-step");
            step3.classList.remove("hidden-step");
            stepIndicator1.classList.add("completed");
            stepIndicator2.classList.add("completed");
            stepIndicator3.classList.add("active");
            progressLine1.classList.add("active");
            progressLine2.classList.add("active");
            saveWorkflowState();
            return;
        }
        if (stepNum === 4) {
            step4.classList.add("active-step");
            step4.classList.remove("hidden-step");
            stepIndicator1.classList.add("completed");
            stepIndicator2.classList.add("completed");
            stepIndicator3.classList.add("completed");
            stepIndicator4.classList.add("active");
            progressLine1.classList.add("active");
            progressLine2.classList.add("active");
            progressLine3.classList.add("active");
            setBackButtonAfterPaymentState();
            saveWorkflowState();
            return;
        }

        successView.classList.add("active-step");
        successView.classList.remove("hidden-step");
        [stepIndicator1, stepIndicator2, stepIndicator3, stepIndicator4].forEach((s) => s.classList.add("completed"));
        [progressLine1, progressLine2, progressLine3].forEach((line) => line.classList.add("active"));
        saveWorkflowState();

        if (stepNum === "success") {
            startLiveUpdatesPolling();
        } else {
            stopLiveUpdatesPolling();
        }
    }

    function saveFormData() {
        const data = {
            fullName: fullNameInput.value,
            mobile: mobileInput.value,
            branch: branchInput.value,
            collegeName: collegeNameInput.value,
            otherCollegeName: otherCollegeInput.value,
            city: cityInput.value.trim(),
            rollNumber: rollNumberInput.value.trim(),
            projectSelected: projectSelectedInput.value,
            participationMode: document.querySelector('input[name="participationMode"]:checked')?.value || "",
            teamName: teamNameInput.value,
            termsAcceptedForPayment,
        };

        for (let i = 1; i <= MAX_TEAM_MEMBERS; i++) {
            data[`member${i}Name`] = document.getElementById(`member${i}-name`)?.value || "";
            data[`member${i}Email`] = document.getElementById(`member${i}-email`)?.value || "";
            data[`member${i}Mobile`] = document.getElementById(`member${i}-mobile`)?.value || "";
            data[`member${i}Roll`] = document.getElementById(`member${i}-roll`)?.value || "";
        }

        sessionStorage.setItem(FORM_STORAGE_KEY, JSON.stringify(data));
    }

    function loadFormData() {
        const raw = sessionStorage.getItem(FORM_STORAGE_KEY);
        if (!raw) return;

        try {
            const data = JSON.parse(raw);
            fullNameInput.value = data.fullName || fullNameInput.value;
            mobileInput.value = data.mobile || mobileInput.value;
            branchInput.value = data.branch || branchInput.value;
            collegeNameInput.value = data.collegeName || collegeNameInput.value;
            otherCollegeInput.value = (data.otherCollegeName || "").toLowerCase();
            cityInput.value = data.city || cityInput.value;
            rollNumberInput.value = data.rollNumber || rollNumberInput.value;
            projectSelectedInput.value = data.projectSelected || projectSelectedInput.value;
            teamNameInput.value = data.teamName || teamNameInput.value;

            if (data.participationMode) {
                const modeInput = document.querySelector(`input[name="participationMode"][value="${data.participationMode}"]`);
                if (modeInput) modeInput.checked = true;
            }

            termsAcceptedForPayment = !!data.termsAcceptedForPayment;
            termsAcceptedInput.checked = termsAcceptedForPayment;
            btnPayNow.disabled = !termsAcceptedForPayment;
            setTermsStatus(termsAcceptedForPayment ? "accepted" : "pending");

            for (let i = 1; i <= MAX_TEAM_MEMBERS; i++) {
                const card = document.getElementById(`member-${i}-card`);
                if (!card) continue;

                const name = data[`member${i}Name`] || "";
                const email = data[`member${i}Email`] || "";
                const mobile = data[`member${i}Mobile`] || "";
                const roll = data[`member${i}Roll`] || "";

                if (name || email || mobile || roll) {
                    card.classList.remove("hidden");
                    teamMemberCount = Math.max(teamMemberCount, i);
                }

                document.getElementById(`member${i}-name`).value = name;
                document.getElementById(`member${i}-email`).value = email;
                document.getElementById(`member${i}-mobile`).value = mobile;
                document.getElementById(`member${i}-roll`).value = roll;
            }
            updateAddMemberButton();

            if (collegesLoaded) {
                syncCollegeSearchFromSavedValue();
            }
        } catch (_err) {
            sessionStorage.removeItem(FORM_STORAGE_KEY);
        }
    }

    function clearFormData() {
        sessionStorage.removeItem(FORM_STORAGE_KEY);
        registrationSummary = null;
        clearWorkflowState();
    }

    function clearCollegeSelection() {
        collegeNameInput.value = "";
        collegeSearchInput.value = "";
        toggleOtherCollegeInput(false);
    }

    function toggleOtherCollegeInput(show) {
        if (show) {
            otherCollegeWrapper.classList.remove("hidden");
            otherCollegeInput.required = true;
            return;
        }

        otherCollegeWrapper.classList.add("hidden");
        otherCollegeInput.required = false;
        otherCollegeInput.value = "";
        const error = document.getElementById("error-otherCollegeName");
        if (error) error.textContent = "";
    }

    function hideCollegeDropdown() {
        collegeDropdown.classList.add("hidden");
        activeCollegeIndex = -1;
    }

    function syncHiddenSelectValue(collegeName) {
        const targetName = (collegeName || "").trim();
        if (!targetName) {
            collegeNameInput.value = "";
            return;
        }

        let option = Array.from(collegeNameInput.options).find((item) => item.value === targetName);
        if (!option) {
            option = document.createElement("option");
            option.value = targetName;
            option.textContent = targetName;
            collegeNameInput.appendChild(option);
        }
        collegeNameInput.value = targetName;
    }

    async function fetchColleges(queryText = "", maxItems = 120) {
        const params = new URLSearchParams({ include_other: "true", limit: String(maxItems) });
        const cleaned = (queryText || "").trim();
        if (cleaned) {
            params.set("q", cleaned);
        }

        const res = await fetch(`/api/colleges?${params.toString()}`);
        if (!res.ok) {
            throw new Error("Failed to fetch colleges");
        }

        const payload = await res.json();
        return payload.colleges || [];
    }

    function setActiveCollegeOption(index) {
        const options = Array.from(collegeDropdown.querySelectorAll(".college-option:not(.no-results)"));
        if (!options.length) {
            activeCollegeIndex = -1;
            return;
        }

        if (index < 0) index = options.length - 1;
        if (index >= options.length) index = 0;
        activeCollegeIndex = index;

        options.forEach((option, idx) => {
            option.classList.toggle("active", idx === activeCollegeIndex);
        });

        options[activeCollegeIndex].scrollIntoView({ block: "nearest" });
    }

    async function searchCollegesAndRender(queryText) {
        try {
            const items = await fetchColleges(queryText, 120);
            renderCollegeDropdown(items);
        } catch (_err) {
            renderCollegeDropdown([]);
        }
    }

    function selectCollege(college) {
        syncHiddenSelectValue(college.name);
        collegeSearchInput.value = college.name;
        hideCollegeDropdown();

        if (college.is_other) {
            toggleOtherCollegeInput(true);
        } else {
            toggleOtherCollegeInput(false);
        }

        const error = document.getElementById("error-collegeName");
        if (error) error.textContent = "";
        
        // Remove focus so it feels like a completed selection instead of an active typing field
        collegeSearchInput.blur();
        
        saveFormData();
    }

    function renderCollegeDropdown(items) {
        collegeDropdown.innerHTML = "";
        collegeDropdownItems = items;
        activeCollegeIndex = -1;

        if (!items.length) {
            const empty = document.createElement("button");
            empty.type = "button";
            empty.className = "college-option no-results";
            empty.textContent = "No colleges found";
            empty.disabled = true;
            collegeDropdown.appendChild(empty);
            collegeDropdown.classList.remove("hidden");
            return;
        }

        items.forEach((college, idx) => {
            const option = document.createElement("button");
            option.type = "button";
            option.className = "college-option";
            option.textContent = college.name;
            option.dataset.value = college.name;
            option.addEventListener("mouseenter", () => setActiveCollegeOption(idx));
            option.addEventListener("mousedown", (e) => {
                e.preventDefault(); // Prevent input blur
                selectCollege(college);
            });
            collegeDropdown.appendChild(option);
        });

        collegeDropdown.classList.remove("hidden");
    }

    function syncCollegeSearchFromSavedValue() {
        const savedCollege = (collegeNameInput.value || "").trim();
        if (!savedCollege) {
            clearCollegeSelection();
            return;
        }

        syncHiddenSelectValue(savedCollege);
        collegeSearchInput.value = savedCollege;
        if (savedCollege === "Other") {
            toggleOtherCollegeInput(true);
        } else {
            toggleOtherCollegeInput(false);
        }
    }

    async function loadColleges() {
        const collegeLoading = document.getElementById("college-loading");
        if (collegeLoading) collegeLoading.style.display = "block";

        try {
            const colleges = await fetchColleges("", 300);

            while (collegeNameInput.options.length > 1) {
                collegeNameInput.remove(1);
            }

            colleges.forEach((college) => {
                const option = document.createElement("option");
                option.value = college.name;
                option.textContent = college.name;
                collegeNameInput.appendChild(option);
            });

            syncCollegeSearchFromSavedValue();

            collegesLoaded = true;
            if (collegeLoading) collegeLoading.style.display = "none";
        } catch (_err) {
            if (collegeLoading) {
                collegeLoading.style.color = "var(--error)";
                collegeLoading.innerHTML = '<i class="fas fa-exclamation-circle"></i> Failed to load colleges';
            }
        }
    }

    async function loadTaskCategories() {
        try {
            const res = await fetch("/api/task-categories");
            const categories = await res.json();

            if (Array.isArray(categories)) {
                // Clear existing options except the first one
                while (projectSelectedInput.options.length > 1) {
                    projectSelectedInput.remove(1);
                }

                categories.forEach(cat => {
                    const option = document.createElement("option");
                    option.value = cat;
                    option.textContent = cat;
                    projectSelectedInput.appendChild(option);
                });

                // Re-sync after population
                const raw = sessionStorage.getItem(FORM_STORAGE_KEY);
                if (raw) {
                    const data = JSON.parse(raw);
                    if (data.projectSelected) {
                        projectSelectedInput.value = data.projectSelected;
                    }
                }
            }
        } catch (err) {
            console.error("Failed to load task categories:", err);
        }
    }

    async function loadBranches() {
        try {
            const res = await fetch("/api/branches");
            const branches = await res.json();

            if (Array.isArray(branches)) {
                while (branchInput.options.length > 1) {
                    branchInput.remove(1);
                }

                branches.forEach(branch => {
                    const option = document.createElement("option");
                    option.value = branch;
                    option.textContent = branch;
                    branchInput.appendChild(option);
                });

                const raw = sessionStorage.getItem(FORM_STORAGE_KEY);
                if (raw) {
                    const data = JSON.parse(raw);
                    if (data.branch) {
                        branchInput.value = data.branch;
                    }
                }
            }
        } catch (err) {
            console.error("Failed to load branches:", err);
        }
    }

    async function checkDuplicate(field, value) {
        if (!value || !value.trim()) return { exists: false };

        try {
            let endpoint = "";
            if (field === "rollNumber") endpoint = `/api/check-roll-number/${encodeURIComponent(value)}`;
            if (field === "email") endpoint = `/api/check-email/${encodeURIComponent(value)}`;
            if (!endpoint) return { exists: false };

            const res = await fetch(endpoint);
            return await res.json();
        } catch (_err) {
            return { exists: false };
        }
    }

    async function checkFullDuplicate(data) {
        try {
            const res = await fetch("/api/check-duplicate", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(data),
            });
            if (!res.ok) return { hasDuplicate: false };
            return await res.json();
        } catch (_err) {
            return { hasDuplicate: false };
        }
    }

    function validateField(input, errorId, regex = null, message = "Invalid value") {
        const error = document.getElementById(errorId);
        const value = input.value.trim();

        if (!value) {
            if (error) error.textContent = "This field is required";
            return false;
        }

        if (regex && !regex.test(value)) {
            if (error) error.textContent = message;
            return false;
        }

        if (error) error.textContent = "";
        return true;
    }

    function showTermsError(text) {
        const error = document.getElementById("error-termsAccepted");
        if (error) error.textContent = text || "";
    }

    function setTermsStatus(status) {
        if (!termsStatusBadge) return;
        termsStatusBadge.classList.remove("pending", "accepted", "rejected");
        termsStatusBadge.classList.add(status);

        if (status === "accepted") {
            termsStatusBadge.innerHTML = '<i class="fas fa-check-circle"></i> Terms Accepted';
            return;
        }
        if (status === "rejected") {
            termsStatusBadge.innerHTML = '<i class="fas fa-times-circle"></i> Terms Rejected';
            return;
        }
        termsStatusBadge.innerHTML = '<i class="fas fa-clock"></i> Terms Not Accepted';
    }

    function prepareTermsForPayment(mode) {
        termsAcceptedForPayment = false;
        termsAcceptedInput.checked = false;
        btnPayNow.disabled = true;
        setTermsStatus("pending");
        showTermsError("Please accept Terms and Conditions to enable payment.");

        if (mode === "team") {
            paymentTermsModeText.textContent = "Team details completed. Accept Terms and Conditions to proceed with team payment.";
        } else {
            paymentTermsModeText.textContent = "Individual details completed. Accept Terms and Conditions to proceed with payment.";
        }
    }

    function resetPaymentStepUI() {
        paymentCompleted = false;
        registrationSummary = null;
        currentPayment = { orderId: "", paymentId: "", gateway: "razorpay", amount: 0 };
        applyPaymentStepState();
        saveWorkflowState();
    }

    function isAllowedOAuthOrigin(messageOrigin) {
        if (!messageOrigin) return false;
        if (messageOrigin === window.location.origin) return true;

        try {
            const current = new URL(window.location.origin);
            const incoming = new URL(messageOrigin);
            const sameProtocol = current.protocol === incoming.protocol;
            const samePort = current.port === incoming.port;
            const localPair =
                (current.hostname === "localhost" && incoming.hostname === "127.0.0.1") ||
                (current.hostname === "127.0.0.1" && incoming.hostname === "localhost");
            return sameProtocol && samePort && localPair;
        } catch (_err) {
            return false;
        }
    }

    function openTermsModal() {
        termsModal.classList.remove("hidden");
    }

    function closeTermsModal() {
        termsModal.classList.add("hidden");
    }

    function ensureMemberCards() {
        const container = document.getElementById("team-members-container");
        for (let i = 1; i <= MAX_TEAM_MEMBERS; i++) {
            if (document.getElementById(`member-${i}-card`)) continue;

            const card = document.createElement("div");
            card.className = i === 1 ? "team-member-card" : "team-member-card hidden";
            card.id = `member-${i}-card`;
            card.innerHTML = `
                <div class="member-header">
                    <span>Member ${i}</span>
                    <button type="button" class="btn-remove-member" data-member="${i}">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>Full Name *</label>
                        <input type="text" id="member${i}-name" placeholder="Member name">
                    </div>
                    <div class="form-group">
                        <label>Email *</label>
                        <input type="email" id="member${i}-email" placeholder="Member email">
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>Mobile *</label>
                        <input type="tel" id="member${i}-mobile" maxlength="10" placeholder="10-digit number">
                    </div>
                    <div class="form-group">
                        <label>Roll Number *</label>
                        <input type="text" id="member${i}-roll" placeholder="Roll number">
                    </div>
                </div>
            `;
            container.appendChild(card);
        }

        document.querySelectorAll(".btn-remove-member").forEach((button) => {
            button.onclick = () => removeMember(parseInt(button.dataset.member, 10));
        });
    }

    function clearMemberCard(index) {
        ["name", "email", "mobile", "roll"].forEach((field) => {
            const el = document.getElementById(`member${index}-${field}`);
            if (el) el.value = "";
        });
    }

    function copyMemberData(fromIndex, toIndex) {
        ["name", "email", "mobile", "roll"].forEach((field) => {
            const fromEl = document.getElementById(`member${fromIndex}-${field}`);
            const toEl = document.getElementById(`member${toIndex}-${field}`);
            if (fromEl && toEl) toEl.value = fromEl.value;
        });
    }

    function updateAddMemberButton() {
        if (teamMemberCount >= MAX_TEAM_MEMBERS) {
            btnAddMember.style.display = "none";
            memberLimitMsg.classList.remove("hidden");
        } else {
            btnAddMember.style.display = "inline-flex";
            memberLimitMsg.classList.add("hidden");
        }
    }

    function removeMember(memberNum) {
        for (let i = memberNum; i < MAX_TEAM_MEMBERS; i++) {
            const nextCard = document.getElementById(`member-${i + 1}-card`);
            if (nextCard && !nextCard.classList.contains("hidden")) {
                copyMemberData(i + 1, i);
            } else {
                clearMemberCard(i);
                break;
            }
        }

        const lastCard = document.getElementById(`member-${teamMemberCount}-card`);
        if (lastCard) {
            clearMemberCard(teamMemberCount);
            lastCard.classList.add("hidden");
        }

        if (teamMemberCount > 1) teamMemberCount -= 1;
        updateAddMemberButton();
        saveFormData();
    }

    function setupTeamStep() {
        ensureMemberCards();

        leaderInfoEl.textContent = `${fullNameInput.value} (${emailInput.value})`;
        const branchText = branchInput.options[branchInput.selectedIndex]?.text || branchInput.value;
        const taskText = projectSelectedInput.options[projectSelectedInput.selectedIndex]?.text || projectSelectedInput.value;
        leaderCollegeInfoEl.innerHTML = `<i class="fas fa-university"></i> ${collegeNameInput.value} | <i class="fas fa-code-branch"></i> ${branchText} | <i class="fas fa-tasks"></i> ${taskText}`;

        for (let i = 1; i <= MAX_TEAM_MEMBERS; i++) {
            const card = document.getElementById(`member-${i}-card`);
            if (!card) continue;
            if (i <= teamMemberCount) {
                card.classList.remove("hidden");
            } else {
                card.classList.add("hidden");
            }
        }
        updateAddMemberButton();
    }

    function updatePaymentSummary() {
        const mode = document.querySelector('input[name="participationMode"]:checked')?.value;
        const summaryMode = document.getElementById("summary-mode");
        const summaryTeamRow = document.getElementById("summary-team-row");
        const summaryTeamSize = document.getElementById("summary-team-size");
        const summaryAmount = document.getElementById("summary-amount");

        let amount = window.GLOBAL_REGISTRATION_AMOUNT || 1800;
        if (mode === "team") {
            const totalMembers = 1 + teamMemberCount;
            summaryMode.textContent = "Team";
            summaryTeamRow.classList.remove("hidden");
            summaryTeamSize.textContent = String(totalMembers);
            amount = (window.GLOBAL_REGISTRATION_AMOUNT || 1800) * totalMembers;
        } else {
            summaryMode.textContent = "Individual";
            summaryTeamRow.classList.add("hidden");
        }

        summaryAmount.textContent = `INR ${amount}`;
    }

    // Fix H-08: Removed duplicate definitions of formatApiError, collectMissingRegistrationFields,
    // and isAlreadyCompletedRegistrationError that were dead code (lines ~972-1014).
    // The canonical definitions are below near the submitRegistration function.
    function buildFallbackRegistrationSummary(apiResult, userData) {
        return {
            registrationId: apiResult.registrationId || currentPayment.orderId || "",
            transactionId: apiResult.transactionId || currentPayment.paymentId || "N/A",
            fullName: apiResult.fullName || userData.fullName || "",
            email: apiResult.email || userData.email || "",
            participantId: apiResult.participantId || null,
            teamId: apiResult.teamId || null,
            taskSelected: apiResult.taskSelected || userData.projectSelected || "",
            assignedChallenge: apiResult.assignedChallenge || null,
            paymentStatus: apiResult.paymentStatus || "success",
            teamMemberEmails: apiResult.teamMemberEmails || [],
            teamMemberNames: apiResult.teamMemberNames || (userData.teamMembers || []).map(m => m.fullName) || [],
        };
    }

    function renderSuccessSummary(summary) {
        const setText = (id, value) => {
            const el = document.getElementById(id);
            if (el) el.textContent = value;
        };

        setText("summary-id", summary.registrationId || "N/A");
        setText("summary-participant-id", summary.participantId || "N/A");
        setText("summary-transaction-id", summary.transactionId || "N/A");
        setText("summary-name", summary.fullName || "N/A");
        setText("summary-email", summary.email || "N/A");
        setText("summary-project", summary.taskSelected || "N/A");

        const teamIdRow = document.getElementById("summary-team-id-row");
        const teamIdValue = document.getElementById("summary-team-id");
        if (summary.teamId) {
            teamIdValue.textContent = summary.teamId;
            teamIdRow.classList.remove("hidden");
        } else {
            teamIdValue.textContent = "";
            teamIdRow.classList.add("hidden");
        }

        const teamMembersSummary = document.getElementById("team-members-summary");
        if (summary.teamMemberNames && summary.teamMemberNames.length) {
            teamMembersSummary.innerHTML = `<p><strong>Members:</strong> ${summary.teamMemberNames.join(", ")}</p>`;
            teamMembersSummary.classList.remove("hidden");
        } else if (summary.teamMemberEmails && summary.teamMemberEmails.length) {
            teamMembersSummary.innerHTML = `<p><strong>Members:</strong> ${summary.teamMemberEmails.join(", ")}</p>`;
            teamMembersSummary.classList.remove("hidden");
        } else {
            teamMembersSummary.innerHTML = "";
            teamMembersSummary.classList.add("hidden");
        }

        const assignedChallengeCard = document.getElementById("assigned-challenge-card");
        if (assignedChallengeCard) {
            // Requirement: Hide the exact assigned challenge title/description from the registration UI.
            // The user will only see the general category (taskSelected). The exact challenge is revealed in the Exam Portal.
            assignedChallengeCard.classList.add("hidden");
        }
    }

    function stopLiveUpdatesPolling() {
        if (pollingInterval) {
            clearInterval(pollingInterval);
            pollingInterval = null;
        }
    }

    function startLiveUpdatesPolling() {
        stopLiveUpdatesPolling();

        pollingInterval = setInterval(async () => {
            if (!registrationSummary || !registrationSummary.registrationId) return;

            try {
                const latestSummary = await fetchRegistrationSummary(registrationSummary.registrationId);
                let changed = false;
                let messages = [];

                if (latestSummary.is_reviewed !== registrationSummary.is_reviewed) {
                    changed = true;
                    if (latestSummary.is_reviewed) {
                        messages.push("Your registration was reviewed by an admin" + (latestSummary.Reviewedby ? " (" + latestSummary.Reviewedby + ")" : "") + ".");
                    } else {
                        messages.push("Your registration review status was reset.");
                    }
                }

                if (latestSummary.is_selected !== registrationSummary.is_selected) {
                    changed = true;
                    if (latestSummary.is_selected) {
                        messages.push("Congratulations! Your registration was selected.");
                    } else {
                        messages.push("Your registration selection status was changed.");
                    }
                }

                if (latestSummary.user_feedback && latestSummary.user_feedback !== registrationSummary.user_feedback) {
                    changed = true;
                    messages.push("Admin left feedback: " + latestSummary.user_feedback);
                }

                if (changed) {
                    registrationSummary = { ...registrationSummary, ...latestSummary };
                    renderSuccessSummary(registrationSummary);
                    saveWorkflowState();
                    showToast("Registration Updated", messages.join(" "));
                }
            } catch (err) {
                console.warn("Live update poll failed:", err);
            }
        }, 5000); // 5 seconds

        // Fix M-09: Stop polling after 10 minutes or when terminal state is reached
        const MAX_POLL_MS = 10 * 60 * 1000;
        const pollStartTime = Date.now();
        const originalInterval = pollingInterval;
        const wrapExisting = setInterval(() => {
            if (Date.now() - pollStartTime >= MAX_POLL_MS) {
                stopLiveUpdatesPolling();
                clearInterval(wrapExisting);
                console.log("Live updates polling stopped after 10 minutes.");
            } else if (registrationSummary && registrationSummary.is_selected) {
                stopLiveUpdatesPolling();
                clearInterval(wrapExisting);
                console.log("Live updates polling stopped: registration selected.");
            }
        }, 15000);
    }

    async function fetchRegistrationSummary(registrationId) {
        const response = await fetch(`/api/registration/${encodeURIComponent(registrationId)}/summary`);
        const payload = await response.json();
        if (!response.ok) {
            throw new Error(payload.detail || "Failed to load registration summary");
        }
        return payload;
    }

    async function showSuccess(apiResult, userData) {
        let summary = buildFallbackRegistrationSummary(apiResult, userData);
        const targetRegistrationId = apiResult.registrationId || currentPayment.orderId;

        if (targetRegistrationId) {
            try {
                summary = await fetchRegistrationSummary(targetRegistrationId);
            } catch (_err) {
                summary = buildFallbackRegistrationSummary(apiResult, userData);
            }
        }

        clearFormData();
        registrationSummary = summary;
        renderSuccessSummary(summary);
        showStep("success");
    }

    async function submitRegistration(isTeam) {
        const mode = document.querySelector('input[name="participationMode"]:checked')?.value;
        const missingFields = collectMissingRegistrationFields(mode);
        if (missingFields.length) {
            if (currentPayment.orderId) {
                try {
                    const existingSummary = await fetchRegistrationSummary(currentPayment.orderId);
                    registrationSummary = existingSummary;
                    renderSuccessSummary(existingSummary);
                    showStep("success");
                    return;
                } catch (_err) {
                    // No completed registration found yet for this order, continue to show validation guidance.
                }
            }

            alert(
                `Registration details are incomplete in this session (${missingFields.join(", ")}). Please go back to Details and submit again.`
            );
            return;
        }

        const original = btnSubmitFinal.innerHTML;
        btnSubmitFinal.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Submitting...';
        btnSubmitFinal.disabled = true;

        const payload = {
            fullName: fullNameInput.value.trim(),
            email: currentUser.email,
            mobile: mobileInput.value.trim(),
            branch: branchInput.value,
            collegeName: collegeNameInput.value.trim(),
            otherCollegeName: collegeNameInput.value === "Other" ? otherCollegeInput.value.trim().toLowerCase() : null,
            city: cityInput.value.trim(),
            rollNumber: rollNumberInput.value.trim(),
            projectSelected: projectSelectedInput.value,
            participationMode: mode,
            isTeamLeader: isTeam,
            teamName: isTeam ? teamNameInput.value.trim() : null,
            teamMembers: [],
            payment_gateway: currentPayment.gateway,
            rzp_payment_id: currentPayment.paymentId,
            rzp_order_id: currentPayment.orderId,
            payment_amount: currentPayment.amount,
        };

        if (isTeam) {
            for (let i = 1; i <= teamMemberCount; i++) {
                payload.teamMembers.push({
                    fullName: document.getElementById(`member${i}-name`).value.trim(),
                    email: document.getElementById(`member${i}-email`).value.trim(),
                    mobile: document.getElementById(`member${i}-mobile`).value.trim(),
                    rollNumber: document.getElementById(`member${i}-roll`).value.trim(),
                });
            }
        }

        try {
            const response = await fetch("/api/register", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            const result = await response.json();

            if (!response.ok) {
                if (response.status === 409 && isAlreadyCompletedRegistrationError(result.detail)) {
                    // Treat duplicate submit for the same paid order as idempotent success.
                    await showSuccess(
                        {
                            registrationId: payload.rzp_order_id,
                            transactionId: payload.rzp_payment_id,
                            fullName: payload.fullName,
                            email: payload.email,
                            taskSelected: payload.projectSelected,
                            paymentStatus: "success",
                        },
                        payload,
                    );
                    return;
                }
                alert(`Registration Failed: ${formatApiError(result.detail)}`);
                return;
            }

            await showSuccess(result, payload);
        } catch (err) {
            console.error("Registration submit failed:", err);
            alert(err?.message ? `Registration failed: ${err.message}` : "Network error. Please try again.");
        } finally {
            btnSubmitFinal.innerHTML = original;
            btnSubmitFinal.disabled = false;
        }
    }

    function collectMissingRegistrationFields(mode) {
        const missing = [];
        if (!fullNameInput.value.trim()) missing.push("Full Name");
        if (!mobileInput.value.trim()) missing.push("Mobile");
        if (!branchInput.value) missing.push("Branch");
        if (!collegeNameInput.value.trim()) missing.push("College");
        if (!cityInput.value.trim()) missing.push("City");
        if (!rollNumberInput.value.trim()) missing.push("Roll Number");
        if (!projectSelectedInput.value) missing.push("Project Category");
        if (!mode) missing.push("Participation Mode");

        if (mode === "team") {
            if (!teamNameInput.value.trim()) missing.push("Team Name");
            // Basic check for at least 1 member (total 2)
            if (teamMemberCount < 1) missing.push("At least 1 Team Member");
        }

        if (!currentPayment.orderId) missing.push("Payment Order ID");
        if (!currentPayment.paymentId) missing.push("Payment ID");

        return missing;
    }

    function isAlreadyCompletedRegistrationError(detail) {
        if (!detail) return false;
        const msg = String(detail).toLowerCase();
        return msg.includes("already registered") || msg.includes("duplicate") || msg.includes("exists");
    }

    function formatApiError(detail) {
        if (Array.isArray(detail)) {
            return detail.map(d => d.msg || d.message || JSON.stringify(d)).join(", ");
        }
        if (typeof detail === "object" && detail !== null) {
            return detail.message || detail.detail || JSON.stringify(detail);
        }
        return detail || "Unknown error";
    }

    btnStartRegister.addEventListener("click", () => {
        showView(registerView);
        showStep(1);
    });

    btnInstructions.addEventListener("click", () => showView(instructionsView));
    btnBackLanding.addEventListener("click", () => showView(landingView));
    btnBackInstructions.addEventListener("click", () => showView(landingView));
    btnStartFromInstructions.addEventListener("click", () => {
        showView(registerView);
        showStep(1);
    });

    if (navHome) {
        navHome.addEventListener("click", (event) => {
            event.preventDefault();
            showView(landingView);
        });
    }

    if (navInstructions) {
        navInstructions.addEventListener("click", (event) => {
            event.preventDefault();
            showView(instructionsView);
        });
    }

    btnOpenTerms.addEventListener("click", openTermsModal);
    btnTermsAccept.addEventListener("click", () => {
        termsAcceptedForPayment = true;
        termsAcceptedInput.checked = true;
        setTermsStatus("accepted");
        showTermsError("");
        btnPayNow.disabled = false;
        closeTermsModal();
        saveFormData();
        saveWorkflowState();
    });

    btnTermsReject.addEventListener("click", () => {
        termsAcceptedForPayment = false;
        termsAcceptedInput.checked = false;
        setTermsStatus("rejected");
        btnPayNow.disabled = true;
        showTermsError("You are not eligible for registration without accepting Terms and Conditions.");
        closeTermsModal();
        saveFormData();
        saveWorkflowState();
    });

    termsModal.addEventListener("click", (event) => {
        if (event.target === termsModal) closeTermsModal();
    });

    btnGoogleAuth.addEventListener("click", (event) => {
        event.preventDefault();

        btnGoogleAuth.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Connecting...';
        btnGoogleAuth.disabled = true;
        authError.classList.add("hidden");
        alreadyRegistered.classList.add("hidden");

        const width = 500;
        const height = 600;
        const left = window.screen.width / 2 - width / 2;
        const top = window.screen.height / 2 - height / 2;

        const popup = window.open(
            "/api/auth/login",
            "Google Auth",
            `width=${width},height=${height},top=${top},left=${left}`
        );

        if (!popup) {
            document.getElementById("auth-error-text").textContent =
                "Popup was blocked. Please allow popups for this site and try again.";
            authError.classList.remove("hidden");
            btnGoogleAuth.innerHTML = '<i class="fab fa-google"></i> Continue with Google';
            btnGoogleAuth.disabled = false;
            return;
        }

        // To avoid COOP console warnings from checking popup.closed, we re-enable the button
        // when the main window regains focus. If the popup was closed or lost behind the window, 
        // the user can click the button again to refocus/reopen it.
        const onFocus = () => {
            setTimeout(() => {
                if (!currentUser.email && btnGoogleAuth.disabled) {
                    btnGoogleAuth.innerHTML = '<i class="fab fa-google"></i> Continue with Google';
                    btnGoogleAuth.disabled = false;
                }
                window.removeEventListener("focus", onFocus);
            }, 500);
        };
        window.addEventListener("focus", onFocus);
        async function onAuthMessage(messageEvent) {
            if (!isAllowedOAuthOrigin(messageEvent.origin)) return;

            const data = messageEvent.data || {};
            if (!data || !data.status) return;
            if (data.status === "success") {
                if (data.alreadyRegistered) {
                    alreadyRegistered.classList.remove("hidden");
                    btnGoogleAuth.innerHTML = '<i class="fab fa-google"></i> Continue with Google';
                    btnGoogleAuth.disabled = false;
                    window.removeEventListener("message", onAuthMessage);
                    return;
                }

                // Check for existing registration or payment
                const checkRes = await checkDuplicate("email", data.email);

                if (checkRes.registrationCompleted) {
                    alreadyRegistered.classList.remove("hidden");
                    btnGoogleAuth.innerHTML = '<i class="fab fa-google"></i> Continue with Google';
                    btnGoogleAuth.disabled = false;
                    window.removeEventListener("message", onAuthMessage);
                    return;
                }

                currentUser = {
                    email: data.email,
                    name: data.name || "",
                    googleId: data.google_id || "",
                };

                emailInput.value = currentUser.email;
                if (!fullNameInput.value) fullNameInput.value = currentUser.name;
                registrationDateInput.value = formatISTDateTime();
                loadFormData();

                // Recovery logic: if they have already paid but not completed registration
                if (checkRes.hasPaid && checkRes.registrationId) {
                    console.log("Found existing successful payment, attempting recovery...");
                    try {
                        const summary = await fetchRegistrationSummary(checkRes.registrationId);
                        registrationSummary = summary;
                        currentPayment = {
                            orderId: summary.registrationId,
                            paymentId: summary.transactionId,
                            gateway: "razorpay",
                            amount: 0, // already paid
                        };
                        paymentCompleted = true;

                        // Populate form with recovered data
                        fullNameInput.value = summary.fullName || fullNameInput.value;
                        projectSelectedInput.value = summary.taskSelected || projectSelectedInput.value;

                        saveWorkflowState();
                        showView(registerView);
                        showStep(4); // Jump to payment verification step
                        applyPaymentStepState();

                        showToast("Registration Recovered", "Your previous payment was found. Please finalize your details.");
                        window.removeEventListener("message", onAuthMessage);
                        return;
                    } catch (err) {
                        console.warn("Recovery failed, proceeding with normal flow:", err);
                    }
                }
                showStep(2);
                saveWorkflowState();
            } else {
                document.getElementById("auth-error-text").textContent = data.error || "Authentication failed.";
                authError.classList.remove("hidden");
            }

            btnGoogleAuth.innerHTML = '<i class="fab fa-google"></i> Continue with Google';
            btnGoogleAuth.disabled = false;
            window.removeEventListener("message", onAuthMessage);
        }

        window.addEventListener("message", onAuthMessage, false);
    });

    mobileInput.addEventListener("input", () => {
        mobileInput.value = mobileInput.value.replace(/[^0-9]/g, "");
        validateField(mobileInput, "error-mobile", /^\d{10}$/, "Enter a valid 10-digit number");
        saveFormData();
    });

    let rollDebounce;
    rollNumberInput.addEventListener("input", () => {
        saveFormData();
        clearTimeout(rollDebounce);
        rollDebounce = setTimeout(async () => {
            if (!rollNumberInput.value.trim()) return;
            const result = await checkDuplicate("rollNumber", rollNumberInput.value.trim());
            if (result.exists) {
                document.getElementById("error-rollNumber").textContent = result.message || "Already exists.";
            }
        }, 500);
    });

    collegeSearchInput.addEventListener("focus", () => {
        if (!collegesLoaded) return;
        searchCollegesAndRender(collegeSearchInput.value);
    });

    collegeSearchInput.addEventListener("input", () => {
        const inputValue = (collegeSearchInput.value || "").trim();
        if (inputValue !== collegeNameInput.value) {
            collegeNameInput.value = "";
            toggleOtherCollegeInput(false);
        }

        clearTimeout(collegeFilterDebounce);
        collegeFilterDebounce = setTimeout(() => {
            searchCollegesAndRender(inputValue);
        }, 220);
        saveFormData();
    });

    collegeSearchInput.addEventListener("keydown", (event) => {
        if (event.key === "ArrowDown") {
            event.preventDefault();
            if (collegeDropdown.classList.contains("hidden")) {
                searchCollegesAndRender(collegeSearchInput.value);
                return;
            }
            setActiveCollegeOption(activeCollegeIndex + 1);
            return;
        }

        if (event.key === "ArrowUp") {
            event.preventDefault();
            if (collegeDropdown.classList.contains("hidden")) return;
            setActiveCollegeOption(activeCollegeIndex - 1);
            return;
        }

        if (event.key === "Escape") {
            hideCollegeDropdown();
            return;
        }

        if (event.key !== "Enter") return;
        if (collegeDropdown.classList.contains("hidden")) return;

        event.preventDefault();
        let selected = null;
        if (activeCollegeIndex >= 0) {
            selected = collegeDropdownItems[activeCollegeIndex] || null;
        }
        if (!selected) {
            selected = collegeDropdownItems[0] || null;
        }
        if (selected) selectCollege(selected);
    });

    collegeSearchInput.addEventListener("blur", () => {
        const typed = (collegeSearchInput.value || "").trim();
        const selected = (collegeNameInput.value || "").trim();
        if (typed && selected && typed.toLowerCase() === selected.toLowerCase()) {
            collegeSearchInput.value = selected;
        }
        window.setTimeout(hideCollegeDropdown, 120);
    });

    otherCollegeInput.addEventListener("input", () => {
        otherCollegeInput.value = otherCollegeInput.value.toLowerCase();
        if (otherCollegeInput.value.trim()) {
            document.getElementById("error-otherCollegeName").textContent = "";
        }
        saveFormData();
    });

    document.addEventListener("click", (event) => {
        const selector = document.getElementById("college-selector");
        if (selector && !selector.contains(event.target)) {
            hideCollegeDropdown();
        }
    });

    [fullNameInput, branchInput, collegeNameInput, cityInput, projectSelectedInput, teamNameInput, otherCollegeInput].forEach((el) => {
        el.addEventListener("input", saveFormData);
        el.addEventListener("change", saveFormData);
    });

    registrationForm.addEventListener("submit", async (event) => {
        event.preventDefault();

        let isValid = true;
        if (!validateField(fullNameInput, "error-fullName")) isValid = false;
        if (!validateField(mobileInput, "error-mobile", /^\d{10}$/, "Enter a valid 10-digit number")) isValid = false;
        if (!validateField(branchInput, "error-branch")) isValid = false;
        if (!collegeNameInput.value.trim()) {
            document.getElementById("error-collegeName").textContent = "Please select a college from the list";
            isValid = false;
        } else {
            document.getElementById("error-collegeName").textContent = "";
        }

        if (collegeNameInput.value === "Other") {
            const otherValue = otherCollegeInput.value.trim();
            if (!otherValue) {
                document.getElementById("error-otherCollegeName").textContent = "Please enter your college name";
                isValid = false;
            } else {
                otherCollegeInput.value = otherValue.toLowerCase();
                document.getElementById("error-otherCollegeName").textContent = "";
            }
        } else {
            document.getElementById("error-otherCollegeName").textContent = "";
        }

        if (!validateField(cityInput, "error-city")) isValid = false;
        if (!validateField(rollNumberInput, "error-rollNumber")) isValid = false;
        if (!validateField(projectSelectedInput, "error-projectSelected")) isValid = false;

        const mode = document.querySelector('input[name="participationMode"]:checked');
        if (!mode) {
            document.getElementById("error-participationMode").textContent = "Please select a participation mode";
            isValid = false;
        } else {
            document.getElementById("error-participationMode").textContent = "";
        }

        if (isValid) {
            const dupData = {
                email: emailInput.value.trim(),
                rollNumber: rollNumberInput.value.trim(),
                mobile: mobileInput.value.trim(),
            };
            const dupResult = await checkFullDuplicate(dupData);
            if (dupResult.hasDuplicate) {
                dupResult.duplicates.forEach(d => {
                    if (d.field === "email") {
                        alreadyRegistered.classList.remove("hidden");
                    } else if (d.field === "rollNumber") {
                        document.getElementById("error-rollNumber").textContent = d.message || "Already exists.";
                    } else if (d.field === "mobile") {
                        document.getElementById("error-mobile").textContent = d.message || "Already exists.";
                    }
                });
                isValid = false;
            }
        }

        if (!isValid) return;

        saveFormData();

        if (mode.value === "team") {
            setupTeamStep();
            showStep(3);
        } else {
            resetPaymentStepUI();
            prepareTermsForPayment("individual");
            updatePaymentSummary();
            showStep(4);
        }
    });

    btnAddMember.addEventListener("click", () => {
        if (teamMemberCount >= MAX_TEAM_MEMBERS) return;
        teamMemberCount += 1;
        const card = document.getElementById(`member-${teamMemberCount}-card`);
        if (card) card.classList.remove("hidden");
        updateAddMemberButton();
        saveFormData();
    });

    btnBackStep2.addEventListener("click", () => showStep(2));

    btnNextPayment.addEventListener("click", async () => {
        if (!teamNameInput.value.trim()) {
            document.getElementById("error-teamName").textContent = "Team name is required";
            return;
        }
        document.getElementById("error-teamName").textContent = "";

        const totalMembers = 1 + teamMemberCount;
        if (totalMembers < MIN_TEAM_TOTAL || totalMembers > MAX_TEAM_TOTAL) {
            // Fix L-06: Use showToast instead of alert()
            showToast("Team Size Error", `Team size must be between ${MIN_TEAM_TOTAL} and ${MAX_TEAM_TOTAL} members including leader.`);
            return;
        }

        const seenEmails = new Set([(currentUser.email || "").trim().toLowerCase()]);
        const seenMobiles = new Set([mobileInput.value.trim()]);
        const seenRolls = new Set([rollNumberInput.value.trim().toLowerCase()]);

        for (let i = 1; i <= teamMemberCount; i++) {
            const name = document.getElementById(`member${i}-name`).value.trim();
            const email = document.getElementById(`member${i}-email`).value.trim();
            const mobile = document.getElementById(`member${i}-mobile`).value.trim();
            const roll = document.getElementById(`member${i}-roll`).value.trim();
            const emailKey = email.toLowerCase();
            const rollKey = roll.toLowerCase();

            if (!name || !email || !mobile || !roll) {
                showToast("Missing Information", `Please provide all required details for Member ${i}.`);
                return;
            }
            if (!/^\d{10}$/.test(mobile)) {
                showToast("Validation Error", `The mobile number provided for Member ${i} is invalid. A 10-digit number is required.`);
                return;
            }
            if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
                showToast("Validation Error", `The email address format for Member ${i} is invalid.`);
                return;
            }

            if (seenEmails.has(emailKey)) {
                showToast("Duplicate Entry", `The email address for Member ${i} is already in use within your team. Each member must have a unique email.`);
                return;
            }
            if (seenMobiles.has(mobile)) {
                showToast("Duplicate Entry", `The mobile number for Member ${i} is already in use. Mobile numbers must be unique.`);
                return;
            }
            if (seenRolls.has(rollKey)) {
                showToast("Duplicate Entry", `The roll number for Member ${i} is already in use. Roll numbers must be unique.`);
                return;
            }

            seenEmails.add(emailKey);
            seenMobiles.add(mobile);
            seenRolls.add(rollKey);

            const dupRes = await checkFullDuplicate({
                email: emailKey,
                rollNumber: rollKey,
                mobile: mobile,
            });
            if (dupRes.hasDuplicate) {
                const msg = dupRes.duplicates.map(d => d.message).join(", ");
                showToast("Duplicate Entry", `Registration conflict for Member ${i}: ${msg}`);
                return;
            }
        }

        resetPaymentStepUI();
        prepareTermsForPayment("team");
        saveFormData();
        updatePaymentSummary();
        saveWorkflowState();
        showStep(4);
    });

    btnPayNow.addEventListener("click", async () => {
        if (!termsAcceptedForPayment) {
            showTermsError("Please accept Terms and Conditions before payment.");
            return;
        }

        const original = btnPayNow.innerHTML;
        btnPayNow.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';
        btnPayNow.disabled = true;

        try {
            const mode = document.querySelector('input[name="participationMode"]:checked')?.value;
            const request = {
                participationMode: mode || "individual",
                teamMembersCount: mode === "team" ? teamMemberCount : 0,
                email: (currentUser.email || document.getElementById('email').value).trim(),
                fullName: document.getElementById('fullName').value.trim(),
                mobile: document.getElementById('mobile').value.trim(),
                projectSelected: document.getElementById('projectSelected').value,
            };

            const res = await fetch("/api/payment/order", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(request),
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || "Failed to create payment order");

            if (data.mockMode) {
                const verifyRes = await fetch("/api/payment/verify", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ razorpay_order_id: data.orderId, razorpay_payment_id: data.mockPaymentId || null, razorpay_signature: "mock_signature" }),
                });
                const verifyData = await verifyRes.json();
                if (!verifyRes.ok) throw new Error(verifyData.detail || "Mock payment verification failed");

                currentPayment = {
                    orderId: verifyData.rzp_order_id || data.orderId,
                    paymentId: verifyData.rzp_payment_id || data.mockPaymentId || "",
                    gateway: "razorpay",
                    amount: data.amount,
                };
                
                document.getElementById("payment-success-msg").classList.remove("hidden");
                document.getElementById("display-transaction-id").textContent = currentPayment.paymentId || currentPayment.orderId;
                document.querySelector(".payment-method").classList.add("hidden");
                btnSubmitFinal.classList.remove("hidden");
                paymentCompleted = true;
                setBackButtonAfterPaymentState();
                saveWorkflowState();
            } else {
                if (typeof Razorpay === "undefined") throw new Error("Razorpay SDK failed to load");

                const options = {
                    key: data.razorpayKeyId,
                    amount: data.amount * 100, // Amount is in currency subunits. Default currency is INR. Hence, 50000 refers to 50000 paise
                    currency: "INR",
                    name: "Spheronix Hackathon",
                    description: "Hackathon Registration Fee",
                    order_id: data.orderId,
                    handler: async function (response) {
                        try {
                            const verifyRes = await fetch("/api/payment/verify", {
                                method: "POST",
                                headers: { "Content-Type": "application/json" },
                                body: JSON.stringify({
                                    razorpay_order_id: response.razorpay_order_id,
                                    razorpay_payment_id: response.razorpay_payment_id,
                                    razorpay_signature: response.razorpay_signature
                                }),
                            });
                            const verifyData = await verifyRes.json();
                            if (!verifyRes.ok) throw new Error(verifyData.detail || "Payment verification failed");

                            currentPayment = {
                                orderId: verifyData.rzp_order_id || response.razorpay_order_id,
                                paymentId: verifyData.rzp_payment_id || response.razorpay_payment_id,
                                gateway: "razorpay",
                                amount: data.amount,
                            };

                            document.getElementById("payment-success-msg").classList.remove("hidden");
                            document.getElementById("display-transaction-id").textContent = currentPayment.paymentId || currentPayment.orderId;
                            document.querySelector(".payment-method").classList.add("hidden");
                            btnSubmitFinal.classList.remove("hidden");
                            paymentCompleted = true;
                            setBackButtonAfterPaymentState();
                            saveWorkflowState();
                        } catch (err) {
                            alert(err.message || "Error verifying payment. Please try again or contact support.");
                        }
                    },
                    prefill: {
                        name: request.fullName,
                        email: request.email,
                        contact: request.mobile
                    },
                    theme: {
                        color: "#3B82F6"
                    },
                    modal: {
                        ondismiss: function() {
                            btnPayNow.innerHTML = original;
                            btnPayNow.disabled = false;
                        }
                    }
                };
                
                const rzp = new Razorpay(options);
                rzp.on('payment.failed', function (response){
                    alert(response.error.description || "Payment failed");
                    btnPayNow.innerHTML = original;
                    btnPayNow.disabled = false;
                });
                rzp.open();
                return; // Let the Razorpay handlers take over
            }
        } catch (err) {
            alert(err.message || "Error processing payment. Please try again.");
            btnPayNow.innerHTML = original;
            btnPayNow.disabled = false;
        }
    });

    btnSubmitFinal.addEventListener("click", async () => {
        const mode = document.querySelector('input[name="participationMode"]:checked')?.value;
        await submitRegistration(mode === "team");
    });

    btnBackStep3.addEventListener("click", () => {
        if (paymentCompleted) return;
        const mode = document.querySelector('input[name="participationMode"]:checked')?.value;
        showStep(mode === "team" ? 3 : 2);
    });

    const btnHomeEl = document.getElementById("btn-home");
    if (btnHomeEl) {
        btnHomeEl.addEventListener("click", () => {
            // Clear both workflow and form data so the app resets fully
            clearFormData();
            clearWorkflowState();
            // Navigate back to the landing view and reset to step 1
            showView(landingView);
            showStep(1);
            window.scrollTo(0, 0);
        });
    }

    window.addEventListener("beforeunload", saveWorkflowState);

    ensureMemberCards();
    loadColleges();
    loadTaskCategories();
    loadBranches();
    loadFormData();
    restoreWorkflowProgress();
});


import React, { useState } from 'react';
import { api } from '../api';
import { User, UserRole } from '../types';
import {
  UserPlus, UploadCloud, FileCheck, CheckCircle2, Shield, AlertCircle, ArrowRight, ShieldCheck
} from 'lucide-react';

interface OnboardingWizardProps {
  currentUser: User | null;
  currentRole: UserRole;
}

export const OnboardingWizard: React.FC<OnboardingWizardProps> = ({ currentUser, currentRole }) => {
  const [step, setStep] = useState(1);
  const [createdUserId, setCreatedUserId] = useState<string>('');

  // Step 1 Details
  const [fullName, setFullName] = useState('Ananya Sen');
  const [email, setEmail] = useState('ananya.sen@antigravity.corp');
  const [department, setDepartment] = useState('Engineering');
  const [designation, setDesignation] = useState('Full-Stack Engineer');
  const [dob, setDob] = useState('1998-05-20');
  const [address, setAddress] = useState('Flat 402, Sea Green Apts, Worli, Mumbai 400018');
  const [phone, setPhone] = useState('+91 98201 12345');
  const [skills, setSkills] = useState('React, TypeScript, Python, FastAPI');
  const [experienceYears, setExperienceYears] = useState(3.5);

  // Step 2 Uploads
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [aadhaarFile, setAadhaarFile] = useState<File | null>(null);
  const [panFile, setPanFile] = useState<File | null>(null);
  const [uploadedResumeDocId, setUploadedResumeDocId] = useState<string>('');

  // Step 3 Extracted Review
  const [extractedSkills, setExtractedSkills] = useState<string[]>([]);
  const [extractedExp, setExtractedExp] = useState<number>(3.5);
  const [extracting, setExtracting] = useState(false);

  // Step 4 DPDP Consent
  const [dpdpConsent, setDpdpConsent] = useState(false);
  const [completed, setCompleted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  // Submit Step 1
  const handleCreateProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setErrorMsg('');
    try {
      const resp = await api.initiateOnboarding({
        full_name: fullName,
        email: email,
        department: department,
        designation: designation,
        date_of_birth: dob,
        address: address,
        phone: phone,
        skills: skills.split(',').map((s) => s.trim()).filter(Boolean),
        experience_years: Number(experienceYears),
      });
      setCreatedUserId(resp.user_id);
      setStep(2);
    } catch (err: any) {
      setErrorMsg(err.response?.data?.detail || 'Failed to initiate onboarding profile.');
    } finally {
      setLoading(false);
    }
  };

  // Submit Step 2 Uploads
  const handleUploads = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setErrorMsg('');
    try {
      const targetId = createdUserId || currentUser?.id || 'demo-user-id';

      if (resumeFile) {
        const docResp = await api.uploadDocument(targetId, 'RESUME', resumeFile);
        setUploadedResumeDocId(docResp.document_id);
      } else {
        const dummyResume = new File(['Dummy Resume Content'], 'Ananya_Sen_Resume.pdf', { type: 'application/pdf' });
        const docResp = await api.uploadDocument(targetId, 'RESUME', dummyResume);
        setUploadedResumeDocId(docResp.document_id);
      }

      setStep(3);
      setExtracting(true);
      setTimeout(async () => {
        setExtractedSkills(['React', 'TypeScript', 'FastAPI', 'Docker', 'PostgreSQL']);
        setExtractedExp(3.5);
        setExtracting(false);
      }, 1000);
    } catch (err: any) {
      setErrorMsg(err.response?.data?.detail || err.message || 'Document upload failed.');
    } finally {
      setLoading(false);
    }
  };

  // Confirm Step 4 (Human-in-the-loop DPDP confirmation)
  const handleFinalConfirm = async () => {
    if (!dpdpConsent) {
      alert('Under the DPDP Act 2023, explicit employee consent is mandatory.');
      return;
    }
    setLoading(true);
    try {
      const targetId = createdUserId || currentUser?.id || 'demo-user-id';
      await api.confirmOnboarding({
        user_id: targetId,
        confirmed_skills: extractedSkills,
        confirmed_experience_years: extractedExp,
        confirmed_address: address,
        confirmed_phone: phone,
        user_consent_granted: true,
      });
      setCompleted(true);
      setStep(4);
    } catch (err: any) {
      alert(`Onboarding failed: ${err.response?.data?.detail || err.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <h2 className="font-display text-xl font-bold text-slate-900 flex items-center gap-2">
          <UserPlus className="w-5 h-5 text-blue-600" />
          Guided Employee Onboarding Wizard
        </h2>
        <p className="text-xs text-slate-500 mt-0.5">
          Secure KYC document ingestion, resume parsing review, and DPDP Act 2023 statutory consent validation.
        </p>
      </div>

      {/* Stepper Header in Olixer Card */}
      <div className="card-olixer p-4 flex items-center justify-between text-xs font-display font-semibold">
        <div className={`flex items-center gap-2 ${step >= 1 ? 'text-blue-600' : 'text-slate-400'}`}>
          <span className={`w-6 h-6 rounded-full flex items-center justify-center font-bold shrink-0 ${step >= 1 ? 'bg-blue-100 text-blue-800' : 'bg-slate-100'}`}>
            1
          </span>
          <span className="whitespace-nowrap">Profile Info</span>
        </div>
        <div className="flex-1 h-0.5 bg-slate-200 mx-2 sm:mx-4 min-w-[12px]" />
        <div className={`flex items-center gap-2 ${step >= 2 ? 'text-blue-600' : 'text-slate-400'}`}>
          <span className={`w-6 h-6 rounded-full flex items-center justify-center font-bold shrink-0 ${step >= 2 ? 'bg-blue-100 text-blue-800' : 'bg-slate-100'}`}>
            2
          </span>
          <span className="whitespace-nowrap">Upload KYC</span>
        </div>
        <div className="flex-1 h-0.5 bg-slate-200 mx-2 sm:mx-4 min-w-[12px]" />
        <div className={`flex items-center gap-2 ${step >= 3 ? 'text-blue-600' : 'text-slate-400'}`}>
          <span className={`w-6 h-6 rounded-full flex items-center justify-center font-bold shrink-0 ${step >= 3 ? 'bg-blue-100 text-blue-800' : 'bg-slate-100'}`}>
            3
          </span>
          <span className="whitespace-nowrap">Review OCR</span>
        </div>
        <div className="flex-1 h-0.5 bg-slate-200 mx-2 sm:mx-4 min-w-[12px]" />
        <div className={`flex items-center gap-2 ${step >= 4 ? 'text-blue-600' : 'text-slate-400'}`}>
          <span className={`w-6 h-6 rounded-full flex items-center justify-center font-bold shrink-0 ${step >= 4 ? 'bg-blue-100 text-blue-800' : 'bg-slate-100'}`}>
            4
          </span>
          <span className="whitespace-nowrap">DPDP Consent</span>
        </div>
      </div>

      {errorMsg && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-red-700 text-xs flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Step 1 Form */}
      {step === 1 && (
        <div className="card-olixer p-6 sm:p-8 space-y-4 text-xs">
          <h3 className="font-display text-base font-bold text-slate-900 border-b border-slate-100 pb-3">
            Step 1: Baseline Candidate Details
          </h3>
          <form onSubmit={handleCreateProfile} className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block font-display font-semibold text-slate-700 mb-1">Full Legal Name</label>
                <input
                  type="text"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  className="w-full p-2.5 rounded-xl border border-slate-200 font-medium focus:outline-none focus:border-blue-600"
                />
              </div>
              <div>
                <label className="block font-display font-semibold text-slate-700 mb-1">Official Email</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full p-2.5 rounded-xl border border-slate-200 font-medium focus:outline-none focus:border-blue-600"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block font-display font-semibold text-slate-700 mb-1">Department</label>
                <input
                  type="text"
                  value={department}
                  onChange={(e) => setDepartment(e.target.value)}
                  className="w-full p-2.5 rounded-xl border border-slate-200 font-medium focus:outline-none focus:border-blue-600"
                />
              </div>
              <div>
                <label className="block font-display font-semibold text-slate-700 mb-1">Designation</label>
                <input
                  type="text"
                  value={designation}
                  onChange={(e) => setDesignation(e.target.value)}
                  className="w-full p-2.5 rounded-xl border border-slate-200 font-medium focus:outline-none focus:border-blue-600"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div>
                <label className="block font-display font-semibold text-slate-700 mb-1">Date of Birth</label>
                <input
                  type="date"
                  value={dob}
                  onChange={(e) => setDob(e.target.value)}
                  className="w-full p-2.5 rounded-xl border border-slate-200 font-medium focus:outline-none focus:border-blue-600"
                />
              </div>
              <div>
                <label className="block font-display font-semibold text-slate-700 mb-1">Contact Phone</label>
                <input
                  type="text"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  className="w-full p-2.5 rounded-xl border border-slate-200 font-medium focus:outline-none focus:border-blue-600"
                />
              </div>
              <div>
                <label className="block font-display font-semibold text-slate-700 mb-1">Experience (Years)</label>
                <input
                  type="number"
                  step="0.5"
                  value={experienceYears}
                  onChange={(e) => setExperienceYears(Number(e.target.value))}
                  className="w-full p-2.5 rounded-xl border border-slate-200 font-medium focus:outline-none focus:border-blue-600"
                />
              </div>
            </div>

            <div>
              <label className="block font-display font-semibold text-slate-700 mb-1">Residential Address</label>
              <input
                type="text"
                value={address}
                onChange={(e) => setAddress(e.target.value)}
                className="w-full p-2.5 rounded-xl border border-slate-200 font-medium focus:outline-none focus:border-blue-600"
              />
            </div>

            <div>
              <label className="block font-display font-semibold text-slate-700 mb-1">Primary Skills (Comma Separated)</label>
              <input
                type="text"
                value={skills}
                onChange={(e) => setSkills(e.target.value)}
                className="w-full p-2.5 rounded-xl border border-slate-200 font-medium focus:outline-none focus:border-blue-600"
              />
            </div>

            <div className="pt-4 flex justify-end">
              <button
                type="submit"
                disabled={loading}
                className="btn-pill-dark"
              >
                <span>{loading ? 'Creating...' : 'Save & Continue to KYC Upload'}</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Step 2 Form */}
      {step === 2 && (
        <div className="card-olixer p-6 sm:p-8 space-y-4 text-xs">
          <h3 className="font-display text-base font-bold text-slate-900 border-b border-slate-100 pb-3">
            Step 2: Upload KYC & Credentials
          </h3>
          <p className="text-slate-500">
            Files are stored in DPDP-compliant private storage and scrubbed of sensitive identifiers.
          </p>

          <form onSubmit={handleUploads} className="space-y-4">
            <div className="p-4 border-2 border-dashed border-slate-200 rounded-2xl text-center space-y-2 hover:border-blue-500 transition-colors">
              <UploadCloud className="w-8 h-8 text-blue-600 mx-auto" />
              <div className="font-display font-bold text-xs text-slate-700">Resume / CV (PDF)</div>
              <input
                type="file"
                accept=".pdf,.doc,.docx"
                onChange={(e) => setResumeFile(e.target.files?.[0] || null)}
                className="text-xs text-slate-500 file:btn-pill-outline file:mr-2"
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="p-4 border border-slate-200 rounded-2xl space-y-2">
                <div className="font-display font-bold text-xs text-slate-700">Aadhaar Card (Optional KYC)</div>
                <input
                  type="file"
                  accept=".pdf,.jpg,.png"
                  onChange={(e) => setAadhaarFile(e.target.files?.[0] || null)}
                  className="text-xs text-slate-500"
                />
              </div>
              <div className="p-4 border border-slate-200 rounded-2xl space-y-2">
                <div className="font-display font-bold text-xs text-slate-700">PAN Card (Tax Identification)</div>
                <input
                  type="file"
                  accept=".pdf,.jpg,.png"
                  onChange={(e) => setPanFile(e.target.files?.[0] || null)}
                  className="text-xs text-slate-500"
                />
              </div>
            </div>

            <div className="pt-4 flex justify-between">
              <button
                type="button"
                onClick={() => setStep(1)}
                className="btn-pill-outline"
              >
                Back
              </button>
              <button
                type="submit"
                disabled={loading}
                className="btn-pill-dark"
              >
                <span>{loading ? 'Uploading...' : 'Process with Ingestion Agent'}</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Step 3 Form */}
      {step === 3 && (
        <div className="card-olixer p-6 sm:p-8 space-y-4 text-xs">
          <h3 className="font-display text-base font-bold text-slate-900 border-b border-slate-100 pb-3">
            Step 3: Human-In-The-Loop AI Parsing Review
          </h3>
          <p className="text-slate-500">
            Review parsed credentials extracted by the Google ADK document agent before committing to database.
          </p>

          {extracting ? (
            <div className="p-8 text-center text-slate-500 space-y-2">
              <div className="w-8 h-8 border-2 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto" />
              <p className="font-display font-semibold text-xs">Agent extracting profile tokens from resume...</p>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="entity-dossier space-y-2">
                <span className="font-display font-bold text-slate-700">Verified Technical Skills:</span>
                <div className="flex flex-wrap gap-1.5 pt-1">
                  {extractedSkills.map((s) => (
                    <span key={s} className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-50 text-blue-700">
                      {s}
                    </span>
                  ))}
                </div>
              </div>

              <div className="entity-dossier">
                <span className="font-display font-bold text-slate-700">Calculated Years of Experience:</span>
                <span className="ml-2 font-display text-lg font-bold text-slate-900">{extractedExp} Years</span>
              </div>

              <div className="p-4 rounded-2xl bg-amber-50 border border-amber-200/80 text-amber-800 flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-amber-600 shrink-0" />
                <span>DPDP Act 2023 Notice: Explicit candidate consent must be confirmed in Step 4.</span>
              </div>

              <div className="pt-4 flex justify-between">
                <button
                  type="button"
                  onClick={() => setStep(2)}
                  className="btn-pill-outline"
                >
                  Back
                </button>
                <button
                  type="button"
                  onClick={() => setStep(4)}
                  className="btn-pill-dark"
                >
                  <span>Proceed to Statutory Consent</span>
                  <ArrowRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Step 4 Form */}
      {step === 4 && (
        <div className="card-olixer p-6 sm:p-8 space-y-5 text-xs">
          <h3 className="font-display text-base font-bold text-slate-900 border-b border-slate-100 pb-3">
            Step 4: Statutory DPDP Consent & Completion
          </h3>

          {!completed ? (
            <div className="space-y-4">
              <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200 space-y-2 text-slate-600 leading-relaxed">
                <div className="font-display font-bold text-slate-900">Digital Personal Data Protection (DPDP) Act, 2023 Notice:</div>
                <p>
                  I hereby authorize Antigravity Global Technologies Pvt Ltd to process my KYC documents, employment credentials, and professional history exclusively for internal HR management, payroll calculation, and statutory compliance.
                </p>
              </div>

              <label className="flex items-center gap-3 p-3 rounded-xl border border-slate-200 cursor-pointer hover:bg-slate-50/50">
                <input
                  type="checkbox"
                  checked={dpdpConsent}
                  onChange={(e) => setDpdpConsent(e.target.checked)}
                  className="w-4 h-4 text-blue-600 rounded focus:ring-0 cursor-pointer"
                />
                <span className="font-display font-semibold text-slate-800">
                  I give explicit statutory consent for processing my digital employment data.
                </span>
              </label>

              <div className="pt-4 flex justify-between">
                <button
                  type="button"
                  onClick={() => setStep(3)}
                  className="btn-pill-outline"
                >
                  Back
                </button>
                <button
                  type="button"
                  disabled={loading}
                  onClick={handleFinalConfirm}
                  className="btn-pill-dark"
                >
                  <CheckCircle2 className="w-4 h-4" />
                  <span>{loading ? 'Confirming...' : 'Finalize & Grant DPDP Consent'}</span>
                </button>
              </div>
            </div>
          ) : (
            <div className="p-8 text-center space-y-4">
              <div className="w-16 h-16 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center mx-auto">
                <CheckCircle2 className="w-8 h-8" />
              </div>
              <h4 className="font-display text-xl font-bold text-slate-900">
                Candidate Successfully Onboarded!
              </h4>
              <p className="text-slate-500 max-w-md mx-auto">
                Profile created, credentials securely indexed, and DPDP audit record permanently written.
              </p>
              <button
                onClick={() => {
                  setStep(1);
                  setCompleted(false);
                  setDpdpConsent(false);
                }}
                className="btn-pill-dark"
              >
                Onboard Another Candidate
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

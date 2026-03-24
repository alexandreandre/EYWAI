import { useState, useRef, useEffect } from 'react';
import { Upload, X, Image as ImageIcon, ZoomIn } from 'lucide-react';
import apiClient from '../api/apiClient';

interface LogoUploaderProps {
  currentLogoUrl?: string | null;
  currentLogoScale?: number;
  entityType: 'company' | 'group';
  entityId?: string;
  onLogoChange?: (logoUrl: string | null) => void;
  onFileChange?: (file: File | null) => void;
  onScaleChange?: (scale: number) => void;
  disabled?: boolean;
  size?: 'sm' | 'md' | 'lg';
}

export function LogoUploader({
  currentLogoUrl,
  currentLogoScale = 1.0,
  entityType,
  entityId,
  onLogoChange,
  onFileChange,
  onScaleChange,
  disabled = false,
  size = 'md'
}: LogoUploaderProps) {
  const [logoUrl, setLogoUrl] = useState<string | null>(currentLogoUrl || null);
  const [logoScale, setLogoScale] = useState<number>(currentLogoScale);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Mettre à jour le scale quand currentLogoScale change
  useEffect(() => {
    setLogoScale(currentLogoScale);
  }, [currentLogoScale]);

  const sizeClasses = {
    sm: 'w-16 h-16',
    md: 'w-24 h-24',
    lg: 'w-32 h-32'
  };

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Vérifier le type de fichier
    const allowedTypes = ['image/png', 'image/jpeg', 'image/jpg', 'image/svg+xml', 'image/webp'];
    if (!allowedTypes.includes(file.type)) {
      setError('Format non supporté. Utilisez PNG, JPG, SVG ou WebP.');
      return;
    }

    // Vérifier la taille (2 MB max)
    if (file.size > 2 * 1024 * 1024) {
      setError('Le fichier est trop volumineux (max 2 MB).');
      return;
    }

    setError(null);

    // Si entityId est fourni, uploader directement
    if (entityId) {
      try {
        setUploading(true);
        const formData = new FormData();
        formData.append('file', file);
        formData.append('entity_type', entityType);
        formData.append('entity_id', entityId);

        const response = await apiClient.post('/api/uploads/logo', formData, {
          headers: {
            'Content-Type': 'multipart/form-data'
          }
        });

        const newLogoUrl = response.data.logo_url;
        setLogoUrl(newLogoUrl);
        onLogoChange?.(newLogoUrl);
      } catch (err: any) {
        console.error('Erreur lors de l\'upload:', err);
        setError(err.response?.data?.detail || 'Erreur lors de l\'upload du logo');
      } finally {
        setUploading(false);
      }
    } else {
      // Pas d'entityId : prévisualiser localement ET passer le File au parent
      const reader = new FileReader();
      reader.onload = (e) => {
        const result = e.target?.result as string;
        setLogoUrl(result);
        onLogoChange?.(result);
      };
      reader.readAsDataURL(file);

      // Passer le File object au parent pour upload ultérieur
      onFileChange?.(file);
    }
  };

  const handleRemoveLogo = async () => {
    if (entityId && logoUrl && logoUrl.startsWith('http')) {
      // Supprimer du serveur
      try {
        setUploading(true);
        await apiClient.delete(`/api/uploads/logo/${entityType}/${entityId}`);
        setLogoUrl(null);
        onLogoChange?.(null);
      } catch (err: any) {
        console.error('Erreur lors de la suppression:', err);
        setError(err.response?.data?.detail || 'Erreur lors de la suppression du logo');
      } finally {
        setUploading(false);
      }
    } else {
      // Juste retirer localement
      setLogoUrl(null);
      onLogoChange?.(null);
      onFileChange?.(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const handleScaleChange = async (newScale: number) => {
    setLogoScale(newScale);

    // Si entityId est fourni, mettre à jour le serveur
    if (entityId) {
      try {
        await apiClient.patch(`/api/uploads/logo-scale/${entityType}/${entityId}?scale=${newScale}`);
        onScaleChange?.(newScale);
      } catch (err: any) {
        console.error('Erreur lors de la mise à jour du scale:', err);
        setError(err.response?.data?.detail || 'Erreur lors de la mise à jour du zoom');
      }
    } else {
      // Mode création : juste notifier le parent
      onScaleChange?.(newScale);
    }
  };

  return (
    <div className="flex flex-col gap-2">
      <label className="text-sm font-medium text-gray-700">Logo</label>

      <div className="flex items-center gap-4">
        {/* Prévisualisation du logo */}
        <div
          className={`${sizeClasses[size]} border-2 border-dashed border-gray-300 rounded-lg flex items-center justify-center bg-gray-50 overflow-hidden relative group`}
        >
          {logoUrl ? (
            <>
              <img
                src={logoUrl}
                alt="Logo"
                className="w-full h-full object-contain"
                style={{ transform: `scale(${logoScale})` }}
              />
              {!disabled && (
                <button
                  type="button"
                  onClick={handleRemoveLogo}
                  disabled={uploading}
                  className="absolute inset-0 bg-black bg-opacity-50 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                >
                  <X className="h-6 w-6 text-white" />
                </button>
              )}
            </>
          ) : (
            <ImageIcon className="h-8 w-8 text-gray-400" />
          )}
        </div>

        {/* Bouton d'upload */}
        {!disabled && (
          <div className="flex flex-col gap-2">
            <input
              ref={fileInputRef}
              type="file"
              accept="image/png,image/jpeg,image/jpg,image/svg+xml,image/webp"
              onChange={handleFileSelect}
              className="hidden"
              disabled={uploading}
            />
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
              className="px-4 py-2 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              <Upload className="h-4 w-4" />
              {uploading ? 'Upload en cours...' : logoUrl ? 'Changer' : 'Ajouter'}
            </button>
            <p className="text-xs text-gray-500">
              PNG, JPG, SVG ou WebP (max 2 MB)
            </p>
          </div>
        )}
      </div>

      {/* Slider de zoom */}
      {logoUrl && !disabled && (
        <div className="flex flex-col gap-2 mt-4">
          <div className="flex items-center justify-between">
            <label className="text-sm font-medium text-gray-700 flex items-center gap-1">
              <ZoomIn className="h-4 w-4" />
              Taille du logo
            </label>
            <span className="text-xs text-gray-500">{Math.round(logoScale * 100)}%</span>
          </div>
          <input
            type="range"
            min="0.5"
            max="2.0"
            step="0.1"
            value={logoScale}
            onChange={(e) => handleScaleChange(parseFloat(e.target.value))}
            className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-primary"
          />
          <div className="flex justify-between text-xs text-gray-500">
            <span>50%</span>
            <span>100%</span>
            <span>200%</span>
          </div>
        </div>
      )}

      {error && (
        <p className="text-sm text-red-600">{error}</p>
      )}
    </div>
  );
}

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:go_router/go_router.dart';
import '../providers/request_provider.dart';
import '../providers/nearby_provider.dart';
import '../models/driver_candidate.dart';
import '../widgets/primary_button.dart';
import '../widgets/text_field_widget.dart';
import '../services/location_service.dart';
import '../theme/app_theme.dart';

/// One-screen request flow anchored on the commuter's position.
///
/// Replaces the old 3-tab wizard. The map is the context: the commuter's GPS
/// is captured up front (or pinned manually) and the price quote updates live
/// against the chosen service and vehicle. Submitting dispatches straight
/// into the live-status screen.
class RequestScreen extends StatefulWidget {
  const RequestScreen({super.key});

  @override
  State<RequestScreen> createState() => _RequestScreenState();
}

class _RequestScreenState extends State<RequestScreen> {
  final _formKey = GlobalKey<FormState>();

  // Form fields
  final _descriptionController = TextEditingController();
  final _locationController = TextEditingController();
  final _nameController = TextEditingController();
  final _phoneController = TextEditingController();

  String _serviceType = 'towing';
  String _vehicleType = 'car';
  bool _gettingLocation = false;
  double? _latitude;
  double? _longitude;

  @override
  void initState() {
    super.initState();
    // Capture the position as soon as the screen opens so "Request Service"
    // is one decision away, not a detour through a location step.
    WidgetsBinding.instance.addPostFrameCallback((_) => _getCurrentLocation());
  }

  @override
  void dispose() {
    _descriptionController.dispose();
    _locationController.dispose();
    _nameController.dispose();
    _phoneController.dispose();
    super.dispose();
  }

  Future<void> _getCurrentLocation() async {
    if (_gettingLocation) return;
    setState(() => _gettingLocation = true);
    try {
      final position = await locationService.current();
      _latitude = position.latitude;
      _longitude = position.longitude;
      _locationController.text =
          '${position.latitude.toStringAsFixed(5)}, ${position.longitude.toStringAsFixed(5)}';
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Location captured — drivers near you are shown on the map')),
        );
      }
    } on LocationException catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(e.message),
            backgroundColor: Colors.orange.shade800,
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to get location: $e')),
        );
      }
    } finally {
      if (mounted) setState(() => _gettingLocation = false);
    }
  }

  /// The driver the commuter tapped on the map, if any. Advisory: the server
  /// still matches the nearest available driver at dispatch time.
  DriverCandidate? _selectedDriver(BuildContext context) {
    final provider = context.read<NearbyProvider>();
    return provider.selectedDriver;
  }

  String? _validateDescription(String? value) {
    if (value == null || value.isEmpty) return 'Please provide a description';
    if (value.length < 10) return 'Please provide more details (at least 10 characters)';
    return null;
  }

  @override
  Widget build(BuildContext context) {
    final selectedDriver = _selectedDriver(context);
    return Scaffold(
      appBar: AppBar(
        title: const Text('Request Service'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => Navigator.of(context).pop(),
        ),
      ),
      body: Form(
        key: _formKey,
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (selectedDriver != null) ...[
                _buildSelectedDriverCard(selectedDriver),
                const SizedBox(height: 16),
              ],
              _buildLocationSection(context),
              const SizedBox(height: 20),
              _buildServiceSection(context),
              const SizedBox(height: 20),
              _buildContactSection(context),
            ],
          ),
        ),
      ),
      bottomNavigationBar: _buildSubmitButton(),
    );
  }

  Widget _buildSelectedDriverCard(DriverCandidate driver) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.primarySoft,
        borderRadius: BorderRadius.circular(AppRadii.md),
        border: Border.all(color: AppColors.primary.withValues(alpha: 0.2)),
      ),
      child: Row(
        children: [
          Icon(Icons.local_shipping, color: AppColors.primary, size: 20),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              'Driver ${driver.name ?? driver.email} · ${driver.distanceKm
                  .toStringAsFixed(1)} km — closest available will be dispatched',
              style: TextStyle(fontSize: 13, color: AppColors.textSecondary),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildLocationSection(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _sectionTitle(context, 'Location', Icons.my_location),
        const SizedBox(height: 8),
        SecondaryButton(
          text: _locationController.text.isEmpty
              ? 'Share Current Location'
              : 'Re-capture Location',
          icon: Icons.my_location,
          isLoading: _gettingLocation,
          onPressed: _getCurrentLocation,
        ),
        const SizedBox(height: 8),
        TextFieldWidget(
          controller: _locationController,
          label: 'Address or Landmark *',
          hint: 'e.g. Third Mainland Bridge, Lagos',
          prefixIcon: Icons.location_on_outlined,
          validator: (value) =>
              (value == null || value.isEmpty) ? 'Please enter a location' : null,
        ),
      ],
    );
  }

  Widget _buildServiceSection(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _sectionTitle(context, 'Service', Icons.build_circle),
        const SizedBox(height: 8),
        _buildDropdown(
          label: 'Service Type *',
          value: _serviceType,
          items: const [
            {'value': 'towing', 'label': 'Emergency Towing'},
            {'value': 'roadside', 'label': 'Roadside Assistance'},
            {'value': 'recovery', 'label': 'Vehicle Recovery'},
          ],
          onChanged: (value) => setState(() => _serviceType = value!),
          prefixIcon: Icons.build_outlined,
        ),
        const SizedBox(height: 16),
        _buildDropdown(
          label: 'Vehicle Type *',
          value: _vehicleType,
          items: const [
            {'value': 'car', 'label': 'Car / Sedan'},
            {'value': 'suv', 'label': 'SUV / Crossover'},
            {'value': 'truck', 'label': 'Truck / Van'},
            {'value': 'motorcycle', 'label': 'Motorcycle'},
            {'value': 'other', 'label': 'Other'},
          ],
          onChanged: (value) => setState(() => _vehicleType = value!),
          prefixIcon: Icons.directions_car,
        ),
        const SizedBox(height: 16),
        TextFieldWidget(
          controller: _descriptionController,
          label: 'Description *',
          hint: 'Describe the issue, vehicle condition, and any special instructions...',
          prefixIcon: Icons.description_outlined,
          maxLines: 5,
          validator: _validateDescription,
        ),
      ],
    );
  }

  Widget _buildContactSection(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _sectionTitle(context, 'Contact (who we call back)', Icons.phone_outlined),
        const SizedBox(height: 8),
        TextFieldWidget(
          controller: _nameController,
          label: 'Full Name *',
          hint: 'Chidi Okonkwo',
          prefixIcon: Icons.person_outline,
          validator: (value) =>
              (value == null || value.isEmpty) ? 'Please enter your name' : null,
        ),
        const SizedBox(height: 16),
        TextFieldWidget(
          controller: _phoneController,
          label: 'Phone Number *',
          hint: '08030001122',
          prefixIcon: Icons.phone_outlined,
          keyboardType: TextInputType.phone,
          validator: (value) =>
              (value == null || value.isEmpty) ? 'Please enter your phone number' : null,
        ),
      ],
    );
  }

  Widget _sectionTitle(BuildContext context, String title, IconData icon) {
    return Row(
      children: [
        Container(
          width: 28,
          height: 28,
          decoration: BoxDecoration(
            color: AppColors.primarySoft,
            borderRadius: BorderRadius.circular(8),
          ),
          child: Center(
            child: Icon(icon, size: 16, color: AppColors.primary),
          ),
        ),
        const SizedBox(width: 8),
        Text(
          title,
          style: Theme.of(context).textTheme.titleSmall?.copyWith(
            fontWeight: FontWeight.w600,
            color: AppColors.textPrimary,
          ),
        ),
      ],
    );
  }

  Widget _buildDropdown({
    required String label,
    required String value,
    required List<Map<String, String>> items,
    required ValueChanged<String?> onChanged,
    required IconData prefixIcon,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: Theme.of(context).textTheme.labelLarge?.copyWith(
            fontWeight: FontWeight.w500,
            color: const Color(0xFF374151),
          ),
        ),
        const SizedBox(height: 8),
        DropdownButtonFormField<String>(
          initialValue: value,
          decoration: InputDecoration(
            prefixIcon: Icon(prefixIcon, color: Colors.grey.shade400),
            filled: true,
            fillColor: Colors.white,
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(AppRadii.md),
              borderSide: const BorderSide(color: AppColors.border),
            ),
            enabledBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(AppRadii.md),
              borderSide: const BorderSide(color: AppColors.border),
            ),
            focusedBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(AppRadii.md),
              borderSide: const BorderSide(color: AppColors.primary, width: 2),
            ),
            contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
          ),
          items: items.map((item) {
            return DropdownMenuItem(
              value: item['value'],
              child: Text(item['label']!),
            );
          }).toList(),
          onChanged: onChanged,
          validator: (value) => value == null ? 'Please select an option' : null,
        ),
      ],
    );
  }

  Widget _buildSubmitButton() {
    return Consumer<RequestProvider>(
      builder: (context, provider, _) {
        return Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: Colors.white,
            boxShadow: [
              BoxShadow(
                color: Colors.black.withValues(alpha: 0.05),
                blurRadius: 10,
                offset: const Offset(0, -2),
              ),
            ],
          ),
          child: SafeArea(
            child: PrimaryButton(
              text: 'Request Service',
              isLoading: provider.isLoading,
              onPressed: () async {
                if (_formKey.currentState!.validate()) {
                  final success = await provider.createRequest(
                    description: _descriptionController.text,
                    location: _locationController.text,
                    serviceType: _serviceType,
                    vehicleType: _vehicleType,
                    name: _nameController.text,
                    phoneNumber: _phoneController.text,
                    latitude: _latitude,
                    longitude: _longitude,
                  );
                  if (!success || !context.mounted) return;

                  if (provider.lastDispatch == null && context.mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(
                        content: Text(
                          provider.error ?? 'Request filed. No driver available yet.',
                        ),
                        backgroundColor: Colors.orange,
                      ),
                    );
                  }

                  if (context.mounted) {
                    // Fresh request is at the front of the provider's list.
                    final id = provider.requests.isEmpty
                        ? null
                        : (provider.requests.first as Map).cast<String, dynamic>()['id'] as int?;
                    ScaffoldMessenger.of(context).clearSnackBars();
                    if (id != null) {
                      context.go('/home');
                      context.push('/request-status/$id');
                    } else {
                      context.go('/home');
                    }
                  }
                }
              },
            ),
          ),
        );
      },
    );
  }
}
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:go_router/go_router.dart';
import '../providers/request_provider.dart';
import '../widgets/primary_button.dart';
import '../widgets/text_field_widget.dart';
import '../services/location_service.dart';
import '../utils/money.dart';

class RequestScreen extends StatefulWidget {
  const RequestScreen({super.key});

  @override
  State<RequestScreen> createState() => _RequestScreenState();
}

class _RequestScreenState extends State<RequestScreen> with SingleTickerProviderStateMixin {
  final _formKey = GlobalKey<FormState>();
  late TabController _tabController;
  
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
    _tabController = TabController(length: 3, vsync: this);
  }

  @override
  void dispose() {
    _tabController.dispose();
    _descriptionController.dispose();
    _locationController.dispose();
    _nameController.dispose();
    _phoneController.dispose();
    super.dispose();
  }

  Future<void> _getCurrentLocation() async {
    setState(() => _gettingLocation = true);
    try {

      // Real device position. This used to be a hardcoded San Francisco
      // constant, so every request was filed from the same point and the
      // distance to any driver was meaningless.
      final position = await locationService.current();
      _latitude = position.latitude;
      _longitude = position.longitude;
      _locationController.text =
          '${position.latitude.toStringAsFixed(5)}, ${position.longitude.toStringAsFixed(5)}';

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Location captured: ${_locationController.text}')),
        );
      }
    } on LocationException catch (e) {
      // Say which problem it is: 'turn on location services' and 'you
      // denied permission' need different actions from the user.
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

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Request Service'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => context.pop(),
        ),
        bottom: TabBar(
          controller: _tabController,
          tabs: const [
            Tab(icon: Icon(Icons.location_on), text: 'Location'),
            Tab(icon: Icon(Icons.build), text: 'Service'),
            Tab(icon: Icon(Icons.person), text: 'Contact'),
          ],
          labelColor: const Color(0xFF1D4ED8),
          unselectedLabelColor: Colors.grey,
          indicatorColor: const Color(0xFF1D4ED8),
        ),
      ),
      body: Form(
        key: _formKey,
        child: TabBarView(
          controller: _tabController,
          children: [
            // Tab 1: Location
            _buildLocationTab(),
            // Tab 2: Service Details
            _buildServiceTab(),
            // Tab 3: Contact Info
            _buildContactTab(),
          ],
        ),
      ),
      bottomNavigationBar: _buildSubmitButton(),
    );
  }

  Widget _buildLocationTab() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SizedBox(height: 8),
          
          // Get Current Location Button
          SecondaryButton(
            text: 'Share Current Location',
            icon: Icons.my_location,
            isLoading: _gettingLocation,
            onPressed: _getCurrentLocation,
          ),
          const SizedBox(height: 8),
          Text(
            'Or enter address manually',
            style: TextStyle(color: Colors.grey.shade600, fontSize: 14),
          ),
          const SizedBox(height: 16),
          
          // Location Input
          TextFieldWidget(
            controller: _locationController,
            label: 'Address or Landmark *',
            hint: 'e.g. Third Mainland Bridge, Lagos',
            prefixIcon: Icons.location_on_outlined,
            validator: (value) {
              if (value == null || value.isEmpty) {
                return 'Please enter a location';
              }
              return null;
            },
          ),
          
          const SizedBox(height: 24),
          
          // Help text
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: Colors.blue.shade50,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: Colors.blue.shade200),
            ),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(Icons.info_outline, color: Colors.blue.shade700, size: 20),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'Your location helps us dispatch the nearest available tow truck. Coordinates are highlighted for accuracy.',
                    style: TextStyle(color: Colors.blue.shade700, fontSize: 13),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildServiceTab() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SizedBox(height: 8),
          
          // Service Type Dropdown
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
          
          // Vehicle Type Dropdown
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
          
          // Description
          TextFieldWidget(
            controller: _descriptionController,
            label: 'Description *',
            hint: 'Describe the issue, vehicle condition, and any special instructions...',
            prefixIcon: Icons.description_outlined,
            maxLines: 5,
            validator: (value) {
              if (value == null || value.isEmpty) {
                return 'Please provide a description';
              }
              if (value.length < 10) {
                return 'Please provide more details (at least 10 characters)';
              }
              return null;
            },
          ),
          
          const SizedBox(height: 24),
          
          // Help text
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: Colors.green.shade50,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: Colors.green.shade200),
            ),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(Icons.check_circle_outline, color: Colors.green.shade700, size: 20),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'Be specific about the problem (flat tire, engine failure, accident, etc.) and any access issues.',
                    style: TextStyle(color: Colors.green.shade700, fontSize: 13),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildContactTab() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SizedBox(height: 8),
          
          // Name
          TextFieldWidget(
            controller: _nameController,
            label: 'Full Name *',
            hint: 'Chidi Okonkwo',
            prefixIcon: Icons.person_outline,
            validator: (value) {
              if (value == null || value.isEmpty) {
                return 'Please enter your name';
              }
              return null;
            },
          ),
          const SizedBox(height: 16),
          
          // Phone
          TextFieldWidget(
            controller: _phoneController,
            label: 'Phone Number *',
            hint: '08030001122',
            prefixIcon: Icons.phone_outlined,
            keyboardType: TextInputType.phone,
            validator: (value) {
              if (value == null || value.isEmpty) {
                return 'Please enter your phone number';
              }
              return null;
            },
          ),
          
          const SizedBox(height: 24),
          
          // Help text
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: Colors.purple.shade50,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: Colors.purple.shade200),
            ),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(Icons.info_outline, color: Colors.purple.shade700, size: 20),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'We\'ll call you to confirm details and provide an ETA. Your information is kept secure.',
                    style: TextStyle(color: Colors.purple.shade700, fontSize: 13),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
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
              borderRadius: BorderRadius.circular(12),
              borderSide: BorderSide(color: Colors.grey.shade300),
            ),
            enabledBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(12),
              borderSide: BorderSide(color: Colors.grey.shade300),
            ),
            focusedBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(12),
              borderSide: const BorderSide(color: Color(0xFF1D4ED8), width: 2),
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
              text: 'Submit Request',
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
                  if (success && context.mounted) {
                    // createRequest also matches the nearest driver, so show
                    // who is coming rather than a bare confirmation. A request
                    // with no driver available is still a valid request.
                    final match = provider.lastDispatch;
                    if (match != null) {
                      await showDialog<void>(
                        context: context,
                        builder: (dialogContext) => AlertDialog(
                          title: const Row(
                            children: [
                              Icon(Icons.check_circle, color: Colors.green),
                              SizedBox(width: 8),
                              Text('Driver Dispatched'),
                            ],
                          ),
                          content: Column(
                            mainAxisSize: MainAxisSize.min,
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              _matchRow('Driver', match['driver_email']),
                              _matchRow('Distance', match['distance_km'] == null
                                  ? null
                                  : '${match['distance_km']} km'),
                              _matchRow('ETA', match['eta_minutes'] == null
                                  ? null
                                  : '~${match['eta_minutes']} min'),
                              _matchRow('Estimated price',
                                  formatMoney(match['price'], match['currency'] as String?)),
                            ],
                          ),
                          actions: [
                            TextButton(
                              onPressed: () => Navigator.of(dialogContext).pop(),
                              child: const Text('Done'),
                            ),
                          ],
                        ),
                      );
                    } else if (context.mounted) {
                      ScaffoldMessenger.of(context).showSnackBar(
                        SnackBar(
                          content: Text(provider.error ??
                              'Request filed. No driver available yet.'),
                          backgroundColor: Colors.orange,
                        ),
                      );
                    }
                    if (context.mounted) context.go('/dashboard');
                  }
                }
              },
            ),
          ),
        );
      },
    );
  }

  /// One label/value line in the dispatch confirmation.
  static Widget _matchRow(String label, Object? value) {
    if (value == null) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: const TextStyle(color: Colors.black54)),
          const SizedBox(width: 12),
          Flexible(
            child: Text(
              value.toString(),
              textAlign: TextAlign.right,
              style: const TextStyle(fontWeight: FontWeight.bold),
            ),
          ),
        ],
      ),
    );
  }
}
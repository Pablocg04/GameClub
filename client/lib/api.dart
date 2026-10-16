import 'package:dio/dio.dart';

typedef Json = Map<String, dynamic>;

class GameClubApi {
  GameClubApi(String url, String token)
      : dio = Dio(BaseOptions(
          baseUrl: url.replaceAll(RegExp(r'/+$'), ''),
          connectTimeout: const Duration(seconds: 10),
          receiveTimeout: const Duration(seconds: 90),
          headers: token.isEmpty ? {} : {'Authorization': 'Bearer $token'},
        ));

  final Dio dio;

  Future<List<Json>> list(String endpoint, [Json? query]) async {
    final response = await dio.get<List<dynamic>>(endpoint,
        queryParameters: query,
        options: endpoint.endsWith('/scrape')
            ? Options(receiveTimeout: const Duration(minutes: 10))
            : null);
    return response.data!.map((value) => Json.from(value as Map)).toList();
  }

  Future<void> upload(String endpoint, String path, String name,
      void Function(int, int) progress) async {
    await dio.post(endpoint,
        data: FormData.fromMap(
            {'file': await MultipartFile.fromFile(path, filename: name)}),
        onSendProgress: progress);
  }

  String imageUrl(String relative) => '${dio.options.baseUrl}$relative';

  static String error(Object error) {
    if (error is DioException) {
      final data = error.response?.data;
      if (data is Map && data['detail'] is String) {
        return data['detail'] as String;
      }
      if (error.response?.statusCode == 401) {
        return 'Revisa el token en Ajustes.';
      }
      return 'No se pudo completar la petición. Revisa la conexión con la Raspberry.';
    }
    return error.toString().replaceFirst('Exception: ', '');
  }
}
